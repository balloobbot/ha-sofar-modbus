"""Config entry diagnostics — the raw register map, for an issue report
showing exactly what the device answered.
https://home-assistant-libs.github.io/modbus-connection/home-assistant/integration/#diagnostics
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from modbus_connection import ModbusError

from .coordinator import SofarConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: SofarConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    device = coordinator.device
    report = coordinator.data
    served = (report.updated | set(report.failed)) if report else set()

    # Reads fresh, not coordinator.data, so the dump reflects live register
    # state at download time.
    registers: dict[str, dict[int, int | bool]] = {}
    read_errors: dict[str, str] = {}
    try:
        registers = await device.async_read_raw()
    except ModbusError as err:
        read_errors["device"] = str(err)

    return {
        "model": device.model,
        "serial_number": device.serial_number,
        "inverter_type": repr(device.inverter_type),
        "served_components": sorted(served),
        "read_errors": read_errors,
        "registers": registers,
    }
