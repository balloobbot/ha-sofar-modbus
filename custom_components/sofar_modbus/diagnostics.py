"""Config entry diagnostics — the raw register map, for an issue report
showing exactly what the device answered.
https://home-assistant-libs.github.io/modbus-connection/home-assistant/integration/#diagnostics

SofarInverter itself has no async_read_raw() — it stopped wrapping a
ComponentGroup when polling moved to independent per-component reads (see
CHANGELOG 0.1.7) — so this reads each served component individually and
merges the raw maps itself, the same per-component iteration coordinator.py
already does.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from modbus_connection import ModbusError

from .const import DOMAIN
from .coordinator import SofarDataUpdateCoordinator


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coordinator: SofarDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    report = coordinator.data
    served = (report.updated | set(report.failed)) if report else set()

    # Reads fresh, not coordinator.data, so the dump reflects live register
    # state at download time — a component's own failure here doesn't fail
    # the whole download, just leaves its registers out with the reason.
    registers: dict[str, dict[int, int | bool]] = {}
    read_errors: dict[str, str] = {}
    for name in sorted(served):
        try:
            raw = await getattr(device, name).async_read_raw()
        except ModbusError as err:
            read_errors[name] = str(err)
            continue
        for space, values in raw.items():
            registers.setdefault(space, {}).update(values)

    return {
        "model": device.model,
        "serial_number": device.serial_number,
        "inverter_type": repr(device.inverter_type),
        "served_components": sorted(served),
        "read_errors": read_errors,
        "registers": registers,
    }
