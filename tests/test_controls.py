"""Tests for Sofar Modbus select, number, switch, and button platforms."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from modbus_connection import ModbusConnectionError
from modbus_connection.encode import encode_int
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant_custom_component.common import MockConfigEntry
from sofar_modbus.modern import PowerControlFlags

from custom_components.sofar_modbus.const import CONF_MODBUS_ADDR, CONF_READ_EPS, DOMAIN
from custom_components.sofar_modbus.coordinator import SofarDataUpdateCoordinator

MOCK_CONFIG = {
    "name": "Sofar Inverter",
    "host": "192.168.1.100",
    "port": 502,
    CONF_MODBUS_ADDR: 1,
    CONF_READ_EPS: True,
}


def _seed_pv_inverter(unit: MockModbusUnit, serial: str = "SS2ES104N5S445") -> None:
    padded = serial.ljust(14, "\x00")
    for i in range(7):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        unit.holding[0x445 + i] = (hi << 8) | lo
    unit.holding[0x0404] = 2  # Running
    unit.holding[0x0484] = 5000  # 50.00 Hz
    unit.holding[0x1104] = 1  # remote switch -> On
    unit.holding[0x1023] = 0  # feed-in limitation -> Disabled
    unit.holding[0x1024] = 44  # feed-in max power -> 4400 W
    unit.holding[0x1105] = 0  # power control -> nothing armed
    unit.holding[0x1106] = 1000  # active power export limit -> 100.0 %


def _seed_hybrid_inverter(unit: MockModbusUnit, serial: str = "SP1XXES100XX") -> None:
    padded = serial.ljust(14, "\x00")
    for i in range(7):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        unit.holding[0x445 + i] = (hi << 8) | lo
    unit.holding[0x0404] = 2
    unit.holding[0x0484] = 5000
    unit.holding[0x1110] = 1  # Charger: TIME_OF_USE (Time Of Use)
    unit.holding[0x1029] = 2  # EPS: TURN_ON_ENABLE_COLD_START
    unit.holding[0x102A] = 0  # EPS wait time
    unit.holding[0x1184] = 600  # passive timeout, 600s
    unit.holding[0x1185] = 1  # passive timeout action: RETURN_TO_PREVIOUS_MODE
    for addr, word in zip(range(0x1187, 0x1189), encode_int(-2000, count=2), strict=True):
        unit.holding[addr] = word
    for addr, word in zip(range(0x1189, 0x118B), encode_int(0, count=2), strict=True):
        unit.holding[addr] = word
    for addr, word in zip(range(0x118B, 0x118D), encode_int(3000, count=2), strict=True):
        unit.holding[addr] = word


async def test_pv_controls_lifecycle(hass: HomeAssistant) -> None:
    """Test remote switch, feed-in, and active power control entities on a PV inverter."""
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

    ent_reg = er.async_get(hass)
    coordinator: SofarDataUpdateCoordinator = entry.runtime_data

    # 1. Remote Switch (immediate write)
    remote_select_id = ent_reg.async_get_entity_id("select", DOMAIN, "SS2ES104N5S445_remote_switch_on_off")
    assert remote_select_id is not None
    assert (state := hass.states.get(remote_select_id)) is not None
    assert state.state == "on"

    # Select Off
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": remote_select_id, "option": "off"},
        blocking=True,
    )
    assert unit.holding[0x1104] == 0
    assert (state := hass.states.get(remote_select_id)) is not None
    assert state.state == "off"

    # Test error handling on invalid option
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": remote_select_id, "option": "InvalidOption"},
            blocking=True,
        )

    # 2. Feed-In Limitation Staging & Button Commit
    feedin_mode_id = ent_reg.async_get_entity_id("select", DOMAIN, "SS2ES104N5S445_feedin_limitation_mode")
    feedin_max_power_id = ent_reg.async_get_entity_id("number", DOMAIN, "SS2ES104N5S445_feedin_max_power")
    feedin_button_id = ent_reg.async_get_entity_id("button", DOMAIN, "SS2ES104N5S445_feedin_update")

    assert feedin_mode_id is not None
    assert feedin_max_power_id is not None
    assert feedin_button_id is not None
    assert (mode_state := hass.states.get(feedin_mode_id)) is not None
    assert mode_state.state == "disabled"
    assert (power_state := hass.states.get(feedin_max_power_id)) is not None
    assert float(power_state.state) == 4400

    # Stage new limitation mode and max power
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": feedin_mode_id, "option": "enabled_feed_in_limitation"},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": feedin_max_power_id, "value": 3000},
        blocking=True,
    )

    # Values in holding registers not written yet (staging pattern)
    assert unit.holding[0x1023] == 0
    assert unit.holding[0x1024] == 44
    assert coordinator.pending["feedin_limitation_mode"] == 1
    assert coordinator.pending["feedin_max_power"] == 3000

    # Press Update Button to commit
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": feedin_button_id},
        blocking=True,
    )
    # Written to registers
    assert unit.holding[0x1023] == 1
    assert unit.holding[0x1024] == 30
    assert "feedin_limitation_mode" not in coordinator.pending
    assert "feedin_max_power" not in coordinator.pending

    # 3. Active Power Control Switch, Number, and Button Commit
    apc_switch_id = ent_reg.async_get_entity_id("switch", DOMAIN, "SS2ES104N5S445_active_power_control_enabled")
    apc_number_id = ent_reg.async_get_entity_id("number", DOMAIN, "SS2ES104N5S445_active_power_export_limit")
    apc_button_id = ent_reg.async_get_entity_id("button", DOMAIN, "SS2ES104N5S445_active_power_control_update")

    assert apc_switch_id is not None
    assert apc_number_id is not None
    assert apc_button_id is not None
    assert (sw_state := hass.states.get(apc_switch_id)) is not None
    assert sw_state.state == "off"
    assert (num_state := hass.states.get(apc_number_id)) is not None
    assert float(num_state.state) == 100.0

    # Turn on switch & set export limit to 80%
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": apc_switch_id},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": apc_number_id, "value": 80.0},
        blocking=True,
    )
    assert coordinator.pending["active_power_control_enabled"] is True
    assert coordinator.pending["active_power_export_limit"] == 80.0
    assert unit.holding[0x1105] == 0  # not written yet

    # Press APC Update button
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": apc_button_id},
        blocking=True,
    )
    assert unit.holding[0x1105] == 1  # armed
    assert unit.holding[0x1106] == 800  # 80.0% -> 800
    assert "active_power_control_enabled" not in coordinator.pending
    assert "active_power_export_limit" not in coordinator.pending

    # Turn off switch
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": apc_switch_id},
        blocking=True,
    )
    assert coordinator.pending["active_power_control_enabled"] is False
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": apc_button_id},
        blocking=True,
    )
    assert unit.holding[0x1105] == 0

    # 4. RTC Sync button — upstream's plugin_sofar.py allows this on PV inverters
    # too (only the read-back result sensor is HYBRID-only), so it must exist here.
    rtc_sync_btn_id = ent_reg.async_get_entity_id("button", DOMAIN, "SS2ES104N5S445_rtc_sync")
    assert rtc_sync_btn_id is not None

    with patch.object(coordinator.device, "async_set_time") as mock_set_time:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": rtc_sync_btn_id},
            blocking=True,
        )
    mock_set_time.assert_awaited_once_with()


async def test_hybrid_controls_lifecycle(hass: HomeAssistant) -> None:
    """Test Charger, EPS, and Passive Mode write entities on a Hybrid inverter."""
    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(1)
    _seed_hybrid_inverter(unit)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SP1XXES100XX",
        data=MOCK_CONFIG,
        title="Sofar Hybrid Inverter",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.sofar_modbus.build_connection", return_value=mock_conn):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    ent_reg = er.async_get(hass)
    coordinator: SofarDataUpdateCoordinator = entry.runtime_data

    # 1. Charger Use Mode (immediate write)
    charger_select_id = ent_reg.async_get_entity_id("select", DOMAIN, "SP1XXES100XX_charger_use_mode")
    assert charger_select_id is not None
    assert (ch_state := hass.states.get(charger_select_id)) is not None
    assert ch_state.state == "time_of_use"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": charger_select_id, "option": "self_use"},
        blocking=True,
    )
    assert unit.holding[0x1110] == 0  # SELF_USE = 0

    # 2. EPS Mode (immediate write)
    eps_select_id = ent_reg.async_get_entity_id("select", DOMAIN, "SP1XXES100XX_eps_control")
    assert eps_select_id is not None
    assert (eps_state := hass.states.get(eps_select_id)) is not None
    assert eps_state.state == "turn_on_enable_cold_start"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": eps_select_id, "option": "turn_off"},
        blocking=True,
    )
    assert unit.holding[0x1029] == 0  # TURN_OFF = 0

    # 3. Passive Mode Timeout Action & Timeout Number
    passive_action_id = ent_reg.async_get_entity_id("select", DOMAIN, "SP1XXES100XX_passive_mode_timeout_action")
    passive_timeout_id = ent_reg.async_get_entity_id("number", DOMAIN, "SP1XXES100XX_passive_mode_timeout")
    passive_timeout_btn_id = ent_reg.async_get_entity_id("button", DOMAIN, "SP1XXES100XX_passive_timeout_update")

    assert passive_action_id is not None
    assert passive_timeout_id is not None
    assert passive_timeout_btn_id is not None
    assert (paction_state := hass.states.get(passive_action_id)) is not None
    assert paction_state.state == "return_to_previous_mode"
    assert (ptimeout_state := hass.states.get(passive_timeout_id)) is not None
    assert float(ptimeout_state.state) == 600

    # Stage timeout settings
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": passive_action_id, "option": "force_standby"},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": passive_timeout_id, "value": 300},
        blocking=True,
    )
    assert coordinator.pending["passive_mode_timeout_action"] == 0
    assert coordinator.pending["passive_mode_timeout"] == 300

    # Press commit button
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": passive_timeout_btn_id},
        blocking=True,
    )
    assert unit.holding[0x1184] == 300
    assert unit.holding[0x1185] == 0
    assert "passive_mode_timeout" not in coordinator.pending
    assert "passive_mode_timeout_action" not in coordinator.pending

    # 4. Passive Mode Power Limits (Grid power, Battery Min, Battery Max)
    grid_power_id = ent_reg.async_get_entity_id("number", DOMAIN, "SP1XXES100XX_passive_mode_grid_power")
    bat_min_id = ent_reg.async_get_entity_id("number", DOMAIN, "SP1XXES100XX_passive_mode_battery_power_min")
    bat_max_id = ent_reg.async_get_entity_id("number", DOMAIN, "SP1XXES100XX_passive_mode_battery_power_max")
    passive_power_btn_id = ent_reg.async_get_entity_id("button", DOMAIN, "SP1XXES100XX_passive_power_update")

    assert grid_power_id is not None
    assert bat_min_id is not None
    assert bat_max_id is not None
    assert passive_power_btn_id is not None

    # Stage new power limits
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": grid_power_id, "value": -1500},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": bat_min_id, "value": -500},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": bat_max_id, "value": 2500},
        blocking=True,
    )

    # Press commit button
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": passive_power_btn_id},
        blocking=True,
    )
    assert "passive_mode_grid_power" not in coordinator.pending
    assert "passive_mode_battery_power_min" not in coordinator.pending
    assert "passive_mode_battery_power_max" not in coordinator.pending

    # 5. RTC Sync button (fire-and-forget: no staged value, just "now")
    rtc_sync_btn_id = ent_reg.async_get_entity_id("button", DOMAIN, "SP1XXES100XX_rtc_sync")
    assert rtc_sync_btn_id is not None

    with patch.object(coordinator.device, "async_set_time") as mock_set_time:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": rtc_sync_btn_id},
            blocking=True,
        )
    mock_set_time.assert_awaited_once_with()


async def test_button_errors_when_uninitialized_or_comm_failure(hass: HomeAssistant) -> None:
    """Test button entity error handling when values are missing or modbus fails."""
    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(1)
    _seed_pv_inverter(unit)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SS2ES104N5S445",
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    with patch("custom_components.sofar_modbus.build_connection", return_value=mock_conn):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    ent_reg = er.async_get(hass)
    feedin_button_id = ent_reg.async_get_entity_id("button", DOMAIN, "SS2ES104N5S445_feedin_update")
    assert feedin_button_id is not None

    # 1. Uninitialized values on device raise HomeAssistantError
    coord: SofarDataUpdateCoordinator = entry.runtime_data
    coord.device.feed_in.feedin_limitation_mode = None  # type: ignore[assignment]
    with pytest.raises(HomeAssistantError, match="feed-in limitation has not been read"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": feedin_button_id},
            blocking=True,
        )

    # 2. Modbus error during button write raises HomeAssistantError
    coord.device.feed_in.feedin_limitation_mode = 0  # type: ignore[assignment]
    coord.device.feed_in.feedin_max_power = 4000  # type: ignore[assignment]
    with patch.object(
        coord.device.feed_in,
        "async_write_limit",
        side_effect=ModbusConnectionError("Connection lost during write"),
    ):
        with pytest.raises(HomeAssistantError, match="could not write feed-in limit"):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": feedin_button_id},
                blocking=True,
            )

    # 3. Active Power Control Button errors
    apc_btn_id = ent_reg.async_get_entity_id("button", DOMAIN, "SS2ES104N5S445_active_power_control_update")
    assert apc_btn_id is not None
    coord.device.active_power_control.power_control = None  # type: ignore[assignment]
    with pytest.raises(HomeAssistantError, match="active power control has not been read"):
        await hass.services.async_call("button", "press", {"entity_id": apc_btn_id}, blocking=True)

    coord.device.active_power_control.power_control = PowerControlFlags(0)  # type: ignore[assignment]
    coord.device.active_power_control.active_power_export_limit = 100.0  # type: ignore[assignment]
    with patch.object(
        coord.device.active_power_control,
        "async_write_active_power_limit",
        side_effect=ModbusConnectionError("Write failed"),
    ):
        with pytest.raises(HomeAssistantError, match="could not write active power limit"):
            await hass.services.async_call("button", "press", {"entity_id": apc_btn_id}, blocking=True)


async def test_select_and_hybrid_button_error_branches(hass: HomeAssistant) -> None:
    """Test write error handling on selects (remote, charger, eps) and hybrid buttons."""
    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(1)
    _seed_hybrid_inverter(unit)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SP1XXES100XX",
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    with patch("custom_components.sofar_modbus.build_connection", return_value=mock_conn):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    ent_reg = er.async_get(hass)
    coord: SofarDataUpdateCoordinator = entry.runtime_data

    # Remote switch write error
    remote_id = ent_reg.async_get_entity_id("select", DOMAIN, "SP1XXES100XX_remote_switch_on_off")
    assert remote_id is not None
    with patch.object(coord.device.remote, "write", side_effect=ModbusConnectionError("Remote error")):
        with pytest.raises(HomeAssistantError, match="could not set remote switch"):
            await hass.services.async_call("select", "select_option", {"entity_id": remote_id, "option": "off"}, blocking=True)

    # Charger use mode write error
    charger_id = ent_reg.async_get_entity_id("select", DOMAIN, "SP1XXES100XX_charger_use_mode")
    assert charger_id is not None
    with patch.object(coord.device.charger, "write", side_effect=ModbusConnectionError("Charger error")):
        with pytest.raises(HomeAssistantError, match="could not set charger use mode"):
            await hass.services.async_call(
                "select", "select_option", {"entity_id": charger_id, "option": "self_use"}, blocking=True
            )

    # EPS mode write error
    eps_id = ent_reg.async_get_entity_id("select", DOMAIN, "SP1XXES100XX_eps_control")
    assert eps_id is not None
    with patch.object(coord.device.eps, "async_write_control", side_effect=ModbusConnectionError("EPS error")):
        with pytest.raises(HomeAssistantError, match="could not set EPS mode"):
            await hass.services.async_call("select", "select_option", {"entity_id": eps_id, "option": "turn_off"}, blocking=True)

    # Passive timeout button uninitialized & error
    timeout_btn_id = ent_reg.async_get_entity_id("button", DOMAIN, "SP1XXES100XX_passive_timeout_update")
    assert timeout_btn_id is not None
    coord.device.passive.passive_mode_timeout = None  # type: ignore[assignment]
    with pytest.raises(HomeAssistantError, match="passive-mode timeout has not been read"):
        await hass.services.async_call("button", "press", {"entity_id": timeout_btn_id}, blocking=True)

    coord.device.passive.passive_mode_timeout = 600  # type: ignore[assignment]
    coord.device.passive.passive_mode_timeout_action = 1  # type: ignore[assignment]
    with patch.object(coord.device.passive, "async_write_timeout", side_effect=ModbusConnectionError("Timeout write error")):
        with pytest.raises(HomeAssistantError, match="could not write passive-mode timeout"):
            await hass.services.async_call("button", "press", {"entity_id": timeout_btn_id}, blocking=True)

    # Passive power button uninitialized & error
    power_btn_id = ent_reg.async_get_entity_id("button", DOMAIN, "SP1XXES100XX_passive_power_update")
    assert power_btn_id is not None
    coord.device.passive.passive_mode_grid_power = None  # type: ignore[assignment]
    with pytest.raises(HomeAssistantError, match="passive-mode power setpoints have not been read"):
        await hass.services.async_call("button", "press", {"entity_id": power_btn_id}, blocking=True)

    coord.device.passive.passive_mode_grid_power = 0  # type: ignore[assignment]
    coord.device.passive.passive_mode_battery_power_min = 0  # type: ignore[assignment]
    coord.device.passive.passive_mode_battery_power_max = 0  # type: ignore[assignment]
    with patch.object(coord.device.passive, "async_write_power", side_effect=ModbusConnectionError("Power write error")):
        with pytest.raises(HomeAssistantError, match="could not write passive-mode power setpoints"):
            await hass.services.async_call("button", "press", {"entity_id": power_btn_id}, blocking=True)

    # RTC sync button error
    rtc_sync_btn_id = ent_reg.async_get_entity_id("button", DOMAIN, "SP1XXES100XX_rtc_sync")
    assert rtc_sync_btn_id is not None
    with patch.object(coord.device, "async_set_time", side_effect=ModbusConnectionError("Clock write error")):
        with pytest.raises(HomeAssistantError, match="could not sync inverter clock"):
            await hass.services.async_call("button", "press", {"entity_id": rtc_sync_btn_id}, blocking=True)
