"""Tests for Sofar Modbus diagnostics platform."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sofar_modbus.const import CONF_MODBUS_ADDR, CONF_READ_EPS, DOMAIN
from custom_components.sofar_modbus.diagnostics import async_get_config_entry_diagnostics

MOCK_CONFIG = {
    "name": "Sofar Inverter",
    "host": "192.168.1.100",
    "port": 502,
    CONF_MODBUS_ADDR: 1,
    CONF_READ_EPS: False,
}


def _seed_pv_inverter(unit: MockModbusUnit, serial: str = "SS2ES104N5S445") -> None:
    padded = serial.ljust(14, "\x00")
    for i in range(7):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        unit.holding[0x445 + i] = (hi << 8) | lo
    unit.holding[0x0404] = 2  # Running
    unit.holding[0x0484] = 5000  # 50.00 Hz
    unit.holding[0x0684] = 100  # solar_generation_today


async def test_get_diagnostics(hass: HomeAssistant) -> None:
    """Test diagnostics returns expected dump of raw registers and metadata."""
    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(1)
    _seed_pv_inverter(unit)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SS2ES104N5S445",
        data=MOCK_CONFIG,
        title="Sofar Inverter (4.4 KTLX-G3)",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.sofar_modbus.build_connection", return_value=mock_conn):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["serial_number"] == REDACTED
    assert diag["serial_prefix"] == "SS2ES104N5"
    assert diag["model"] == "4.4 KTLX-G3"
    assert "PV" in diag["inverter_type"]
    assert "grid" in diag["served_components"]
    assert diag["read_errors"] == {}
    assert "holding" in diag["registers"]
    assert 0x0484 in diag["registers"]["holding"]
    # The raw register dump must not leak the serial number either -- those
    # 7 words (the identity block's ASCII encoding of it) are the same value
    # serial_number above gets redacted to.
    for addr in range(0x445, 0x445 + 7):
        assert addr not in diag["registers"]["holding"], f"register {addr:#x} should be stripped (encodes the serial number)"


async def test_get_diagnostics_with_read_error(hass: HomeAssistant) -> None:
    """Test diagnostics captures read error when raw read fails."""
    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(1)
    _seed_pv_inverter(unit)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SS2ES104N5S445",
        data=MOCK_CONFIG,
        title="Sofar Inverter (4.4 KTLX-G3)",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.sofar_modbus.build_connection", return_value=mock_conn):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    # Fail raw read
    with patch.object(
        entry.runtime_data.device,
        "async_read_raw",
        side_effect=ModbusTimeoutError("Timeout reading raw registers"),
    ):
        diag = await async_get_config_entry_diagnostics(hass, entry)

    assert "device" in diag["read_errors"]
    assert "Timeout reading raw registers" in diag["read_errors"]["device"]
