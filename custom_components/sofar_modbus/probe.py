"""Probe a Sofar inverter and classify its model before committing to it.

sofar_modbus.modern.device.SofarInverter.async_setup() doesn't raise on an
unrecognized serial number — it just leaves .inverter_type at InverterType(0),
meaning "no component applies". The config flow and __init__.py both need that
turned into an error instead of silently proceeding with an empty device.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sofar_modbus.modern.device import SofarInverter


class SofarUnrecognizedError(Exception):
    """The device answered, but its serial number matched no known Sofar model."""

    def __init__(self, serial: str) -> None:
        super().__init__(f"unrecognized Sofar inverter, serial number: {serial!r}")
        self.serial = serial


async def async_setup_and_check(device: SofarInverter) -> None:
    """Run SofarInverter.async_setup(), raising SofarUnrecognizedError on no match."""
    await device.async_setup()
    if not device.inverter_type:
        raise SofarUnrecognizedError(device.serial_number or "")
