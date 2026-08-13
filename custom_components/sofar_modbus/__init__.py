"""Sofar Inverter Modbus — built on modbus-connection.

Layering (see modbus-connection's integration guide): this module owns the
ModbusConnection and the coordinator; sofar-modbus is the HA-free device
library that does the actual register work.
"""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from sofar_modbus.modern.device import SofarInverter

from .connection import build_connection, unit_id
from .const import DEFAULT_SCAN_INTERVAL
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    connection = build_connection(entry.data)
    entry.async_on_unload(connection.close)

    unit = connection.for_unit(unit_id(entry.data))
    device = SofarInverter(unit)

    coordinator = SofarDataUpdateCoordinator(hass, entry, connection, device, DEFAULT_SCAN_INTERVAL)
    # async_update() (called for us here) runs async_setup() internally on
    # first use and settles device.inverter_type; ModbusError already maps to
    # ConfigEntryNotReady via first_refresh's own handling, but an
    # unrecognized serial doesn't raise on its own (sofar_modbus just leaves
    # inverter_type at zero), so that still needs an explicit check.
    await coordinator.async_config_entry_first_refresh()
    if not device.inverter_type:
        raise ConfigEntryNotReady(f"unrecognized Sofar inverter, serial number: {device.serial_number!r}")

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
