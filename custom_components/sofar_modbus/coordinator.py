"""DataUpdateCoordinator wrapping SofarInverter.async_update().

sofar_modbus reads each polled component independently and contains a failed
one in its returned UpdateReport rather than failing the whole poll — only a
dead link (ModbusConnectionError) still raises. This coordinator maps that to
UpdateFailed for a dead link, disconnect()s after repeated per-block timeouts
to recover a link that's up but unresponsive (a wedged serial-to-network
bridge), and otherwise stores the report as coordinator.data so entities can
tell which of them, if any, went stale this poll.
https://home-assistant-libs.github.io/modbus-connection/home-assistant/integration/
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusConnection, ModbusError, ModbusTimeoutError

from sofar_modbus.model import UpdateReport
from sofar_modbus.modern.device import SofarInverter

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_TIMEOUT_DISCONNECT_THRESHOLD = 3


class SofarDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Polls one Sofar inverter's components, one at a time."""

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

    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.device.async_update()
        except ModbusError as err:
            # In practice only ModbusConnectionError reaches here — a dead
            # link, not a single bad block, which async_update() already
            # contains into report.failed instead of raising.
            raise UpdateFailed(str(err)) from err

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

        for component_name, cause in report.failed.items():
            _LOGGER.debug(
                "%s: %s did not refresh this poll, keeping its previous values: %s",
                self.name,
                component_name,
                cause,
            )
        return report
