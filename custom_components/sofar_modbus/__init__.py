"""Sofar Inverter Modbus — built on modbus-connection.

Layering (see modbus-connection's integration guide): this module owns the
ModbusConnection and the coordinator; custom_components/sofar_modbus/sofar/
is the HA-free device library that does the actual register work.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from modbus_connection import ModbusError

from .connection import build_connection, unit_id
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import SofarDataUpdateCoordinator
from .sofar.device import SofarInverter, SofarUnrecognizedError, async_probe

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    connection = build_connection(entry.data)
    entry.async_on_unload(connection.close)

    unit = connection.for_unit(unit_id(entry.data))
    try:
        identity = await async_probe(unit)
    except (ModbusError, SofarUnrecognizedError) as err:
        raise ConfigEntryNotReady(f"cannot probe Sofar inverter: {err}") from err

    device = SofarInverter(unit, identity)
    coordinator = SofarDataUpdateCoordinator(hass, entry, connection, device, DEFAULT_SCAN_INTERVAL)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
