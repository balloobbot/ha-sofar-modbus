"""Build a modbus_connection ModbusConnection from a config entry.

TCP only for now — serial and the Home Assistant Core Modbus hub are Phase 3
(see the plan). Constructing a connection performs no I/O; the first request
made against a unit connects on demand.

Uses the tmodbus backend. Note: homeassistant-solax-modbus pins
tmodbus==0.4.1 exactly in its manifest, and Home Assistant's per-integration
requirement installer re-pins tmodbus back to that exact version on every
restart while that integration is loaded — which breaks
modbus_connection.tmodbus (needs tmodbus>=0.5.1) if both run on the same HA
instance. Test this integration on an instance without solax_modbus loaded.
"""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT
from modbus_connection import ModbusConnection as _Base
from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection

from .const import CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR, DEFAULT_PORT


def build_connection(data: dict[str, Any]) -> _Base:
    """Build the connection for a config entry's data (TCP)."""
    return ModbusConnection(
        ModbusTcpParams(
            host=data[CONF_HOST],
            port=data.get(CONF_PORT, DEFAULT_PORT),
        )
    )


def unit_id(data: dict[str, Any]) -> int:
    return int(data.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR))
