"""The Sofar device object — hand-written, on top of the generated components.

Follows the modbus-connection device-object pattern: takes a ModbusUnit, never
a connection or host/port; the consumer owns the connection.
https://home-assistant-libs.github.io/modbus-connection/patterns/library/
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from modbus_connection.model import ComponentGroup

from .components.battery_pack import BatteryPack
from .components.realtime import RealtimeData
from .components.settings import SettingsReadback
from .const import (
    BAT_BTS,
    BATTERY_PACK_ALLOWEDTYPES,
    HYBRID,
    REALTIME_ALLOWEDTYPES,
    SETTINGS_ALLOWEDTYPES,
    determine_inverter_type,
    matches_inverter,
    restrict_names,
)

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

# Serial number is read at a fixed address regardless of model (0x445, ASCII,
# 7 registers) — see async_read_serialnr in the upstream plugin.
_SERIAL_FIELD = "serial_number"


@dataclass(frozen=True)
class SofarIdentity:
    """What async_probe() learns before anything else can be set up."""

    serial: str
    model: str
    invertertype: int

    @property
    def is_hybrid(self) -> bool:
        return bool(self.invertertype & HYBRID)

    @property
    def has_battery_pack_bus(self) -> bool:
        return bool(self.invertertype & BAT_BTS)


class SofarUnrecognizedError(Exception):
    """The device answered, but its serial number matched no known Sofar model."""

    def __init__(self, serial: str) -> None:
        super().__init__(f"unrecognized Sofar inverter, serial number: {serial!r}")
        self.serial = serial


async def async_probe(unit: ModbusUnit) -> SofarIdentity:
    """Read the serial number and classify the inverter. No polling state kept."""
    probe = RealtimeData(unit)
    probe.restrict_fields([_SERIAL_FIELD])
    await probe.async_update()
    serial = (probe.serial_number or "").strip()
    if not serial:
        raise SofarUnrecognizedError(serial="")
    invertertype, model = determine_inverter_type(serial)
    if invertertype == 0:
        raise SofarUnrecognizedError(serial)
    return SofarIdentity(serial=serial, model=model, invertertype=invertertype)


class SofarInverter:
    """A Sofar inverter: real-time telemetry, settings readback, battery pack."""

    def __init__(self, unit: ModbusUnit, identity: SofarIdentity) -> None:
        self._unit = unit
        self.identity = identity

        # Component.restrict_fields() narrows what gets *read*, but
        # deliberately leaves declared_fields describing the full static
        # layout (an excluded field just decodes as None) — see
        # https://home-assistant-libs.github.io/modbus-connection/modelling/restricting-fields/.
        # So `component.declared_fields` can't answer "does this inverter
        # serve this field"; the *_served_keys sets below, computed here
        # before restrict_fields() expands composites, are what entity
        # platforms (sensor.py etc.) must filter against instead.
        served_realtime = [k for k, m in REALTIME_ALLOWEDTYPES.items() if matches_inverter(identity.invertertype, m)]
        served_settings = [k for k, m in SETTINGS_ALLOWEDTYPES.items() if matches_inverter(identity.invertertype, m)]

        self.realtime = RealtimeData(unit)
        self.realtime.restrict_fields(restrict_names(served_realtime))
        self.realtime_served_keys = frozenset(served_realtime)

        self.settings = SettingsReadback(unit)
        self.settings.restrict_fields(restrict_names(served_settings))
        self.settings_served_keys = frozenset(served_settings)

        self.battery_pack: BatteryPack | None = None
        self.battery_pack_served_keys: frozenset[str] = frozenset()
        components = [self.realtime, self.settings]
        if identity.has_battery_pack_bus:
            served_battery = [k for k, m in BATTERY_PACK_ALLOWEDTYPES.items() if matches_inverter(identity.invertertype, m)]
            if served_battery:
                self.battery_pack = BatteryPack(unit)
                self.battery_pack.restrict_fields(restrict_names(served_battery))
                self.battery_pack_served_keys = frozenset(served_battery)
                components.append(self.battery_pack)

        self._group = ComponentGroup(unit, components)

    async def async_update(self) -> None:
        """Refresh every polled component in one pooled set of reads."""
        await self._group.async_update()

    async def async_read_raw(self) -> dict[str, dict[int, int | bool]]:
        """Raw register map for diagnostics — see ComponentGroup.async_read_raw."""
        return await self._group.async_read_raw()
