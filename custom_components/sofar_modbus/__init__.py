"""Sofar Inverter Modbus — built on modbus-connection.

Layering (see modbus-connection's integration guide): this module owns the
ModbusConnection and the coordinator; custom_components/sofar_modbus/sofar/
is the HA-free device library that does the actual register work.
"""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from modbus_connection import ModbusError

from sofar_modbus.modern.device import SofarInverter

from .connection import build_connection, unit_id
from .const import DEFAULT_SCAN_INTERVAL
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator
from .probe import SofarUnrecognizedError, async_setup_and_check

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    connection = build_connection(entry.data)
    entry.async_on_unload(connection.close)

    unit = connection.for_unit(unit_id(entry.data))
    device = SofarInverter(unit)
    try:
        await async_setup_and_check(device)
    except (ModbusError, SofarUnrecognizedError) as err:
        raise ConfigEntryNotReady(f"cannot probe Sofar inverter: {err}") from err

    coordinator = SofarDataUpdateCoordinator(hass, entry, connection, device, DEFAULT_SCAN_INTERVAL)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
