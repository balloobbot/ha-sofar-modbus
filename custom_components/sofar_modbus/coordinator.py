"""The two DataUpdateCoordinators driving one Sofar inverter.

sofar_modbus polls what the inverter measures apart from what it has been told
to do — async_update_readings() and async_update_settings() — and contains
either the same way: a component whose read fails keeps its previous values and
lands in the returned UpdateReport, while a dead link (ModbusConnectionError),
or a timeout before anything answered at all, still raises.

One coordinator drives each half on its own interval: the measurements at the
user's scan interval, the settings every _SETTINGS_INTERVAL — they only change
when something writes them, and this integration refreshes them straight after
its own writes. Each entity attaches to whichever of the two polls reads its
component, so ``available`` follows the poll that actually refreshes it.

Both give a failed component one retry before accepting the failure, mirroring
solax_modbus's transport-level `retries=1` one layer up — modbus_connection
deliberately disables backend retries (see its own commit 115df8b) so a failure
surfaces on the first attempt and "the wrapper alone decides what happens
next"; these coordinators are that wrapper.

Only the measurements coordinator disconnect()s after repeated timed-out polls
to recover a link that's up but unresponsive (a wedged serial-to-network
bridge): a second poller dropping the link under a poll already in flight is a
hazard of its own. The two are safe to run against one connection either way —
the backend serialises requests.
https://home-assistant-libs.github.io/modbus-connection/home-assistant/integration/

``pending`` backs the number/select/switch write entities whose registers the
device only accepts as one combined block (FeedIn limitation, active power
control): those entities stage a value here instead of writing it, and a
paired button entity performs the actual write and clears the keys it just
committed. Every one of them reads a settings component, so it lives on that
coordinator. See pending_or_live().
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, TypeVar, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from modbus_connection import ModbusConnection, ModbusConnectionError, ModbusError, ModbusTimeoutError

from sofar_modbus.model import SofarComponentBase, UpdateReport  # the PyPI library, not a self-import — see __init__.py
from sofar_modbus.modern.device import SofarInverter

_LOGGER = logging.getLogger(__name__)

_TIMEOUT_DISCONNECT_THRESHOLD = 3
_HEALTH_WINDOW = 60  # ~5min at the 5s base scan interval
# An absolute cadence, not a multiple of the scan interval: a setting only
# moves when something writes it, and a write from here refreshes it at once,
# so this poll exists purely to pick up a change made elsewhere (the inverter's
# own display, another Modbus client) within a few minutes.
_SETTINGS_INTERVAL = timedelta(minutes=5)

# What sofar_modbus reads in async_update_settings(); everything else it serves
# is a measurement. The library keeps its two poll lists private and publishes
# only their concatenation (polled_components), so this mirrors them —
# tests/lib/test_coordinator.py pins it against what a settings poll actually
# touches, so the two can't drift apart silently.
SETTINGS_COMPONENTS: frozenset[str] = frozenset(
    {
        "active_power_control",
        "battery_active_control",
        "battery_config",
        "battery_config_id",
        "charger",
        "eps",
        "feed_in",
        "identity",
        "parallel",
        "passive",
        "remote",
        "rtc_sync",
    }
)

type SofarConfigEntry = ConfigEntry[SofarRuntimeData]

_T = TypeVar("_T")


@dataclass
class SofarRuntimeData:
    """Both of an inverter's polls, for the platforms to attach entities to."""

    readings: SofarDataUpdateCoordinator
    settings: SofarSettingsCoordinator

    def coordinator_for(self, component: str) -> SofarCoordinator:
        """Whichever of the two polls reads ``component``."""
        return self.settings if component in SETTINGS_COMPONENTS else self.readings


class SofarCoordinator(DataUpdateCoordinator[UpdateReport]):
    """One half of the device poll, retried once per failed component."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SofarConfigEntry,
        device: SofarInverter,
        name: str,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=name,
            update_interval=update_interval,
        )
        self.device = device
        self._consecutive_failures: dict[str, int] = {}

    @property
    def served_components(self) -> frozenset[str]:
        """All component names served by this inverter type."""
        if self.device.polled_components is not None:
            return frozenset(self.device.polled_components)
        if self.data is not None:
            return frozenset(self.data.updated | set(self.data.failed))
        return frozenset()

    async def _async_poll_device(self) -> UpdateReport:
        """This coordinator's half of the device poll."""
        raise NotImplementedError

    async def _async_poll_raised(self, error: ModbusError) -> None:
        """Bookkeeping for a poll that failed at the link, not per component."""

    def _poll_returned(self, report: UpdateReport) -> None:
        """Bookkeeping for a poll that came back, complete or not."""

    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self._retry_failed(await self._async_poll_device())
        except ModbusError as err:
            # ModbusConnectionError (dead link) reaches here, as does a timeout
            # before anything answered, while per-block failures once alive are
            # contained in UpdateReport.failed.
            await self._async_poll_raised(err)
            raise UpdateFailed(str(err)) from err
        self._poll_returned(report)
        if not report.updated:
            errors = list(report.failed.values())
            if not errors:
                raise UpdateFailed(f"{self.name}: no component answered")
            cause = errors[0] if len(errors) == 1 else ExceptionGroup("all components failed to refresh", errors)
            raise UpdateFailed(f"{self.name}: no component answered: {errors[0]}") from cause
        return report

    async def _retry_failed(self, report: UpdateReport) -> UpdateReport:
        """Give every failed component one more try before accepting the failure.

        Skipped when nothing answered on the first pass (e.g. an all-timeout
        outage) to avoid doubling the timeout latency when the link is down.
        """
        if report.failed and report.updated:
            report = await self._retry(report)

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

    async def _retry(self, report: UpdateReport) -> UpdateReport:
        """One more read of each failed component, notifying at the end the way
        the library's own poll does rather than mid-cycle.
        """
        updated = set(report.updated)
        failed: dict[str, ModbusError] = {}
        for name in report.failed:
            component: SofarComponentBase = getattr(self.device, name)
            try:
                await component.async_update(notify=False)
            except ModbusConnectionError:
                raise
            except ModbusError as err:
                failed[name] = err
            else:
                updated.add(name)
        for name in updated - report.updated:
            getattr(self.device, name).notify()
        return UpdateReport(updated, failed)


class SofarDataUpdateCoordinator(SofarCoordinator):
    """Polls what the inverter measures, at the user's scan interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SofarConfigEntry,
        connection: ModbusConnection,
        device: SofarInverter,
        scan_interval: int,
    ) -> None:
        super().__init__(hass, entry, device, entry.title, timedelta(seconds=scan_interval))
        self.connection = connection
        self._consecutive_timeouts = 0
        self._poll_outcomes: deque[bool] = deque(maxlen=_HEALTH_WINDOW)
        self.last_error: str | None = None
        self.last_error_time: datetime | None = None

    @property
    def success_rate(self) -> float | None:
        """Percent of the last `_HEALTH_WINDOW` poll cycles with no failed component.

        None until the first poll lands. Whole-device, not per-component: a
        cycle only counts as a failure if a component's poll still shows up
        in the returned report.failed after _retry_failed's one retry.
        """
        if not self._poll_outcomes:
            return None
        return round(100 * sum(self._poll_outcomes) / len(self._poll_outcomes), 1)

    def _record_poll_outcome(self, success: bool, error: ModbusError | None) -> None:
        self._poll_outcomes.append(success)
        if error is not None:
            self.last_error = f"{type(error).__name__}: {error}"
            self.last_error_time = dt_util.utcnow()

    async def _async_poll_device(self) -> UpdateReport:
        if self.device.polled_components is None:
            await self.device.async_setup()
        if not self.device.inverter_type:
            # An unrecognized serial serves no component at all; report the
            # identity read that did land, so __init__.py can say so itself
            # instead of this failing as "no component answered".
            return UpdateReport(updated={"identity"}, failed={})
        return await self.device.async_update_readings()

    async def _async_poll_raised(self, error: ModbusError) -> None:
        if isinstance(error, ModbusTimeoutError):
            self._consecutive_timeouts += 1
            if self._consecutive_timeouts >= _TIMEOUT_DISCONNECT_THRESHOLD:
                _LOGGER.debug(
                    "%s: %d consecutive timed-out polls, recycling the connection",
                    self.name,
                    self._consecutive_timeouts,
                )
                await self.connection.disconnect()
                self._consecutive_timeouts = 0
        self._record_poll_outcome(False, error)

    def _poll_returned(self, report: UpdateReport) -> None:
        if report.updated:
            self._consecutive_timeouts = 0
        self._record_poll_outcome(bool(report.updated) and not report.failed, next(iter(report.failed.values()), None))


class SofarSettingsCoordinator(SofarCoordinator):
    """Polls what the inverter has been configured to do, rarely.

    No link recovery of its own — see the module docstring.
    """

    def __init__(self, hass: HomeAssistant, entry: SofarConfigEntry, device: SofarInverter) -> None:
        super().__init__(hass, entry, device, f"{entry.title} settings", _SETTINGS_INTERVAL)
        self.pending: dict[str, Any] = {}

    async def _async_poll_device(self) -> UpdateReport:
        return await self.device.async_update_settings()

    def pending_or_live(self, key: str, live_value: _T) -> _T:
        """What a staged number/select/switch entity should show right now.

        The value the user last set this session, if any and if it hasn't
        been committed yet — otherwise whatever the last successful poll
        read. In-memory only: these registers are volatile on the device
        itself (no flash wear from writing them often), so there's nothing
        to persist across a restart either.
        """
        return cast("_T", self.pending.get(key, live_value))
