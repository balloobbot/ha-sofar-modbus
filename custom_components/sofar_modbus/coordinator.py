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
  from generated_sensors.py's own state_class metadata — read only every
  _SLOW_TIER_EVERY_N_CYCLES-th cycle, cutting total registers read per poll.

Also disconnect()s after repeated per-block timeouts to recover a link
that's up but unresponsive (a wedged serial-to-network bridge), and stores
the report as coordinator.data so entities can tell which of them, if any,
went stale.
https://home-assistant-libs.github.io/modbus-connection/home-assistant/integration/
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusConnection, ModbusConnectionError, ModbusError, ModbusTimeoutError

from sofar_modbus.model import SofarComponentBase, UpdateReport
from sofar_modbus.modern.device import SofarInverter

from .const import DOMAIN
from .generated_sensors import SENSOR_DESCRIPTIONS

_LOGGER = logging.getLogger(__name__)

_TIMEOUT_DISCONNECT_THRESHOLD = 3
_SLOW_TIER_EVERY_N_CYCLES = 4  # ~60s at the 15s base scan interval


def _slow_tier_components() -> frozenset[str]:
    """Component names with no 'measurement' row — settings, counters, identity.

    Derived from generated_sensors.py's own state_class metadata rather than a
    separately hand-maintained list, so there's one source of truth for what
    changes often enough to need every-cycle freshness.
    """
    all_components = {description.component for description in SENSOR_DESCRIPTIONS}
    volatile = {
        description.component for description in SENSOR_DESCRIPTIONS if description.state_class == SensorStateClass.MEASUREMENT
    }
    return frozenset(all_components - volatile)


class SofarDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Polls one Sofar inverter's components, tiered by how often they change."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
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

    async def _async_update_data(self) -> UpdateReport:
        try:
            if self._fast is None:
                report = await self._async_first_poll()
            else:
                report = await self._poll(self._components_due())
            self._cycle += 1
            return await self._retry_failed(report)
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
        slow_names = _slow_tier_components() & served
        self._slow = {name: getattr(self.device, name) for name in slow_names}
        self._fast = {name: getattr(self.device, name) for name in served - slow_names}
        return report

    def _components_due(self) -> dict[str, SofarComponentBase]:
        assert self._fast is not None
        components = dict(self._fast)
        if self._cycle % _SLOW_TIER_EVERY_N_CYCLES == 0:
            assert self._slow is not None
            components.update(self._slow)
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
        """Give every failed component one more try before accepting the failure."""
        if report.failed:
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
            self._consecutive_failures[name] = self._consecutive_failures.get(name, 0) + 1
            _LOGGER.debug(
                "%s: %s did not refresh this poll even after a retry, keeping its previous "
                "values (%d consecutive failures): %s",
                self.name,
                name,
                self._consecutive_failures[name],
                cause,
            )
        for name in report.updated:
            self._consecutive_failures.pop(name, None)

        return report
