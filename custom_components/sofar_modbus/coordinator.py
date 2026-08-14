"""DataUpdateCoordinator wrapping SofarInverter.async_update().

sofar_modbus reads each polled component independently and contains a failed
one in its returned UpdateReport rather than failing the whole poll — only a
dead link (ModbusConnectionError) still raises. This coordinator builds on
that in two ways solax_modbus's production behavior showed were still
missing (see the design note this ships alongside):

- A component that fails gets one retry before it's accepted as failed,
  mirroring solax_modbus's transport-level `retries=1` one layer up —
  modbus_connection deliberately disables backend retries (see its own
  commit 115df8b) so a failure surfaces on the first attempt and "the
  wrapper alone decides what happens next"; this coordinator is that
  wrapper.
- After the first refresh (which still polls everything, the way
  SofarInverter.async_update() does it, to learn what this inverter
  serves), later polls split components into a fast tier (read every
  cycle) and a slow tier — settings, energy counters, identity, derived
  from sensor.py's own state_class metadata — read only every
  _SLOW_TIER_EVERY_N_CYCLES-th cycle, cutting total registers read per poll.

Also disconnect()s after repeated per-block timeouts to recover a link
that's up but unresponsive (a wedged serial-to-network bridge), and stores
the report as coordinator.data so entities can tell which of them, if any,
went stale.
https://home-assistant-libs.github.io/modbus-connection/home-assistant/integration/

``pending`` backs the number/select/switch write entities whose registers the
device only accepts as one combined block (FeedIn limitation, active power
control): those entities stage a value here instead of writing it, and a
paired button entity performs the actual write and clears the keys it just
committed. See pending_or_live().
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusConnection, ModbusConnectionError, ModbusError, ModbusTimeoutError

from sofar_modbus.model import SofarComponentBase, UpdateReport
from sofar_modbus.modern.device import SofarInverter

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_TIMEOUT_DISCONNECT_THRESHOLD = 3
_SLOW_TIER_EVERY_N_CYCLES = 4  # ~60s at the 15s base scan interval

type SofarConfigEntry = ConfigEntry[SofarDataUpdateCoordinator]


def _volatile_components() -> frozenset[str]:
    """Component names with at least one 'measurement' row.

    Derived from sensor.py's own SENSOR_DESCRIPTIONS state_class metadata
    rather than a separately hand-maintained list, so there's one source of
    truth for what changes often enough to need every-cycle freshness.
    Components with only counters/settings or no sensor rows at all (write-only
    components like feed_in, active_power_control, passive, charger, remote)
    join the slow tier.
    Imported here, not at module level: sensor.py imports SofarConfigEntry
    from this module, so a module-level import back would be circular — this
    one only runs when a poll actually needs it, well after both modules have
    finished loading.
    """
    from .sensor import SENSOR_DESCRIPTIONS

    return frozenset(
        description.component
        for description in SENSOR_DESCRIPTIONS
        if description.state_class == SensorStateClass.MEASUREMENT
    )


class SofarDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Polls one Sofar inverter's components, tiered by how often they change."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SofarConfigEntry,
        connection: ModbusConnection,
        device: SofarInverter,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{device.serial_number}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.connection = connection
        self.device = device
        self._consecutive_timeouts = 0
        self._consecutive_failures: dict[str, int] = {}
        self._cycle = 0
        self._fast: dict[str, SofarComponentBase] | None = None
        self._slow: dict[str, SofarComponentBase] | None = None
        self._force_slow_tier = False
        self.pending: dict[str, Any] = {}

    def pending_or_live(self, key: str, live_value: Any) -> Any:
        """What a staged number/select/switch entity should show right now.

        The value the user last set this session, if any and if it hasn't
        been committed yet — otherwise whatever the last successful poll
        read. In-memory only: these registers are volatile on the device
        itself (no flash wear from writing them often), so there's nothing
        to persist across a restart either.
        """
        return self.pending.get(key, live_value)

    async def async_request_refresh(self) -> None:
        self._force_slow_tier = True
        await super().async_request_refresh()

    async def _async_update_data(self) -> UpdateReport:
        try:
            if self._fast is None:
                report = await self._async_first_poll()
            else:
                report = await self._poll(self._components_due())
            self._cycle += 1
            report = await self._retry_failed(report)
            if not report.updated:
                errors = list(report.failed.values())
                cause = errors[0] if len(errors) == 1 else ExceptionGroup("all components failed to refresh", errors)
                raise UpdateFailed(f"{self.name}: no component answered: {errors[0]}") from cause
            return report
        except ModbusError as err:
            # In practice only ModbusConnectionError reaches here — a dead
            # link, not a single bad block, which the poll already contains
            # into UpdateReport.failed instead of raising.
            raise UpdateFailed(str(err)) from err

    async def _async_first_poll(self) -> UpdateReport:
        """Poll everything, the way SofarInverter itself orchestrates it, and
        use what it actually served to settle the fast/slow tier split.
        """
        report = await self.device.async_update()
        served = report.updated | set(report.failed)
        fast_names = _volatile_components() & served
        self._fast = {name: getattr(self.device, name) for name in fast_names}
        self._slow = {name: getattr(self.device, name) for name in served - fast_names}
        return report

    def _components_due(self) -> dict[str, SofarComponentBase]:
        assert self._fast is not None
        components = dict(self._fast)
        if self._force_slow_tier or self._cycle % _SLOW_TIER_EVERY_N_CYCLES == 0:
            assert self._slow is not None
            components.update(self._slow)
            self._force_slow_tier = False
        return components

    async def _poll(self, components: dict[str, SofarComponentBase]) -> UpdateReport:
        """One attempt at each of ``components``, no retry."""
        updated: set[str] = set()
        failed: dict[str, ModbusError] = {}
        for name, component in components.items():
            try:
                await component.async_update()
            except ModbusConnectionError:
                raise
            except ModbusError as err:
                failed[name] = err
            else:
                updated.add(name)
        return UpdateReport(updated, failed)

    async def _retry_failed(self, report: UpdateReport) -> UpdateReport:
        """Give every failed component one more try before accepting the failure.

        Skipped when nothing answered on the first pass (e.g. an all-timeout
        outage) to avoid doubling the timeout latency when the link is down.
        """
        if report.failed and report.updated:
            retry = await self._poll({name: getattr(self.device, name) for name in report.failed})
            report = UpdateReport(report.updated | retry.updated, retry.failed)

        if any(isinstance(cause, ModbusTimeoutError) for cause in report.failed.values()):
            self._consecutive_timeouts += 1
            if self._consecutive_timeouts >= _TIMEOUT_DISCONNECT_THRESHOLD:
                _LOGGER.warning(
                    "%s: %d consecutive polls with a timed-out block, recycling the connection",
                    self.name,
                    self._consecutive_timeouts,
                )
                await self.connection.disconnect()
                self._consecutive_timeouts = 0
        else:
            self._consecutive_timeouts = 0

        for name, cause in report.failed.items():
            prev = self._consecutive_failures.get(name, 0)
            self._consecutive_failures[name] = prev + 1
            if prev == 0:
                _LOGGER.warning(
                    "%s: %s failed to refresh and is keeping its previous values: %s",
                    self.name,
                    name,
                    cause,
                )
        for name in report.updated:
            self._consecutive_failures.pop(name, None)

        return report
