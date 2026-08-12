"""DataUpdateCoordinator wrapping SofarInverter.async_update().

Follows the modbus-connection integration guide: map ModbusError to
UpdateFailed, never reload the entry on a dropped link (reconnection is
automatic), and disconnect() after repeated timeouts to recover a link that
is up but unresponsive (a wedged serial-to-network bridge).
https://home-assistant-libs.github.io/modbus-connection/home-assistant/integration/
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusConnection, ModbusError, ModbusTimeoutError

from .const import DOMAIN
from .sofar.device import SofarInverter

_LOGGER = logging.getLogger(__name__)

_TIMEOUT_DISCONNECT_THRESHOLD = 3


class SofarDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Polls one Sofar inverter's real-time/settings/battery-pack components."""

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
            name=f"{DOMAIN}_{device.identity.serial}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.connection = connection
        self.device = device
        self._consecutive_timeouts = 0

    async def _async_update_data(self) -> None:
        try:
            await self.device.async_update()
        except ModbusTimeoutError as err:
            self._consecutive_timeouts += 1
            if self._consecutive_timeouts >= _TIMEOUT_DISCONNECT_THRESHOLD:
                _LOGGER.warning(
                    "%s: %d consecutive timeouts, recycling the connection",
                    self.name,
                    self._consecutive_timeouts,
                )
                await self.connection.disconnect()
                self._consecutive_timeouts = 0
            raise UpdateFailed(str(err)) from err
        except ModbusError as err:
            raise UpdateFailed(str(err)) from err
        else:
            self._consecutive_timeouts = 0
