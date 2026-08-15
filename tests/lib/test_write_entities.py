"""Standalone script: the select/number/switch/button write entities against
the mock backend — no real Home Assistant required. Covers the staged-write
design: number/select/switch entities only edit coordinator.pending, the
paired button issues the one combined Modbus write and clears it. Safe to run
standalone: `python tests/lib/test_write_entities.py`.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from homeassistant.exceptions import HomeAssistantError  # noqa: E402
from modbus_connection import ModbusError  # noqa: E402
from modbus_connection.encode import encode_int  # noqa: E402
from modbus_connection.mock import MockModbusConnection, MockModbusUnit, WriteEvent  # noqa: E402
from sofar_modbus.modern import ChargerUseMode, EpsControlMode, FeedinLimitationMode, PassiveModeTimeoutAction  # noqa: E402
from sofar_modbus.modern.device import SofarInverter  # noqa: E402

from custom_components.sofar_modbus.button import (  # noqa: E402
    ActivePowerControlUpdateButton,
    FeedInUpdateButton,
    PassivePowerUpdateButton,
    PassiveTimeoutUpdateButton,
)
from custom_components.sofar_modbus.coordinator import SofarDataUpdateCoordinator  # noqa: E402
from custom_components.sofar_modbus.number import (  # noqa: E402
    ActivePowerExportLimitNumber,
    FeedInMaxPowerNumber,
    PassiveBatteryPowerMaxNumber,
    PassiveBatteryPowerMinNumber,
    PassiveGridPowerNumber,
    PassiveTimeoutNumber,
)
from custom_components.sofar_modbus.select import (  # noqa: E402
    ChargerUseModeSelect,
    EpsModeSelect,
    FeedInLimitationModeSelect,
    PassiveTimeoutActionSelect,
    RemoteSwitchSelect,
)
from custom_components.sofar_modbus.switch import ActivePowerControlSwitch  # noqa: E402


class _FakeConnection:
    async def disconnect(self) -> None:
        pass


def _seed_serial(unit: MockModbusUnit, serial: str) -> None:
    padded = serial.ljust(14, "\x00")
    for i in range(7):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        unit.holding[0x445 + i] = (hi << 8) | lo


class _TestCoordinator(SofarDataUpdateCoordinator):
    _refresh_calls: int


async def _device_and_coordinator() -> tuple[SofarInverter, _TestCoordinator]:
    """A PV-only KTLX-G3 (this project's own reference hardware) with remote,
    feed-in and active-power-control all pre-seeded and already polled once.
    """
    unit = MockModbusConnection().for_unit(1)
    _seed_serial(unit, "SS2ES104N5S445")
    unit.holding[0x1104] = 1  # remote switch -> On
    unit.holding[0x1023] = 0  # feed-in limitation -> Disabled
    unit.holding[0x1024] = 44  # feed-in max power -> 4400 W
    unit.holding[0x1105] = 0  # power control -> nothing armed
    unit.holding[0x1106] = 1000  # active power export limit -> 100.0 %

    device = SofarInverter(unit)
    report = await device.async_update()
    assert report.complete, f"unexpected failures against the mock: {report.failed}"
    assert {"remote", "feed_in", "active_power_control"} <= report.updated

    coordinator = _TestCoordinator.__new__(_TestCoordinator)
    coordinator.name = "test"
    coordinator.connection = _FakeConnection()  # type: ignore[assignment]
    coordinator.device = device
    coordinator.config_entry = SimpleNamespace(title="Test Sofar")  # type: ignore[assignment]
    coordinator.data = report
    coordinator.pending = {}
    coordinator._refresh_calls = 0

    async def _fake_refresh() -> None:
        coordinator._refresh_calls += 1

    coordinator.async_request_refresh = _fake_refresh  # type: ignore[method-assign]
    return device, coordinator


async def _hybrid_device_and_coordinator() -> tuple[SofarInverter, _TestCoordinator]:
    """A HYBRID identity (same serial prefix as test_smoke.py's HYBRID run) with
    charger, EPS and passive-mode all pre-seeded and already polled once.

    read_eps=True: without it "eps" never joins ``served``, the same gap that
    left this integration's EPS sensor dead before the read_eps config option
    was added — see const.py's CONF_READ_EPS.
    """
    unit = MockModbusConnection().for_unit(1)
    _seed_serial(unit, "SP1XXES100XX")
    unit.holding[0x1110] = int(ChargerUseMode.TIME_OF_USE)
    unit.holding[0x1029] = int(EpsControlMode.TURN_ON_ENABLE_COLD_START)
    unit.holding[0x102A] = 0  # EPS wait time, reserved
    unit.holding[0x1184] = 600  # passive timeout, seconds
    unit.holding[0x1185] = int(PassiveModeTimeoutAction.RETURN_TO_PREVIOUS_MODE)
    for addr, word in zip(range(0x1187, 0x1189), encode_int(-2000, count=2), strict=True):
        unit.holding[addr] = word
    for addr, word in zip(range(0x1189, 0x118B), encode_int(0, count=2), strict=True):
        unit.holding[addr] = word
    for addr, word in zip(range(0x118B, 0x118D), encode_int(3000, count=2), strict=True):
        unit.holding[addr] = word

    device = SofarInverter(unit, read_eps=True)
    report = await device.async_update()
    assert report.complete, f"unexpected failures against the mock: {report.failed}"
    assert {"charger", "eps", "passive"} <= report.updated

    coordinator = _TestCoordinator.__new__(_TestCoordinator)
    coordinator.name = "test-hybrid"
    coordinator.connection = _FakeConnection()  # type: ignore[assignment]
    coordinator.device = device
    coordinator.config_entry = SimpleNamespace(title="Test Sofar Hybrid")  # type: ignore[assignment]
    coordinator.data = report
    coordinator.pending = {}
    coordinator._refresh_calls = 0

    async def _fake_refresh() -> None:
        coordinator._refresh_calls += 1

    coordinator.async_request_refresh = _fake_refresh  # type: ignore[method-assign]
    return device, coordinator


def _mute_state_writes(entity: object) -> None:
    """Entities aren't added to hass in this test, so async_write_ha_state()
    would raise (it needs self.hass) — stub it, the same way the entity
    itself never writes to the device on a stage, only local state.
    """
    entity.async_write_ha_state = lambda: None  # type: ignore[attr-defined]


async def test_remote_switch_writes_immediately() -> None:
    _, coordinator = await _device_and_coordinator()
    entity = RemoteSwitchSelect(coordinator)
    _mute_state_writes(entity)
    assert entity.current_option == "on"

    events: list[WriteEvent] = []
    coordinator.device.remote.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await entity.async_select_option("off")
    assert [(e.address, e.values) for e in events] == [(0x1104, [0])]
    assert coordinator._refresh_calls == 1
    print("remote-switch-writes-immediately: PASSED")


async def test_feedin_select_and_number_only_stage() -> None:
    _, coordinator = await _device_and_coordinator()
    mode_entity = FeedInLimitationModeSelect(coordinator)
    power_entity = FeedInMaxPowerNumber(coordinator)
    _mute_state_writes(mode_entity)
    _mute_state_writes(power_entity)

    events: list[WriteEvent] = []
    coordinator.device.feed_in.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await mode_entity.async_select_option("enabled_feed_in_limitation")
    await power_entity.async_set_native_value(3000)
    assert not events, "staging must not touch the device"
    assert coordinator.pending == {
        "feedin_limitation_mode": FeedinLimitationMode.ENABLED_FEED_IN_LIMITATION,
        "feedin_max_power": 3000,
    }
    assert mode_entity.current_option == "enabled_feed_in_limitation"
    assert power_entity.native_value == 3000
    print("feedin-select-and-number-only-stage: PASSED")


async def test_feedin_update_button_commits_the_staged_pair() -> None:
    _, coordinator = await _device_and_coordinator()
    coordinator.pending["feedin_limitation_mode"] = FeedinLimitationMode.ENABLED_FEED_IN_LIMITATION
    coordinator.pending["feedin_max_power"] = 3000
    button = FeedInUpdateButton(coordinator)
    _mute_state_writes(button)

    events: list[WriteEvent] = []
    coordinator.device.feed_in.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await button.async_press()
    assert [(e.address, e.values) for e in events] == [(0x1023, [1, 30])]
    assert coordinator.pending == {}, "committed keys must be cleared"
    assert coordinator._refresh_calls == 1
    print("feedin-update-button-commits-the-staged-pair: PASSED")


async def test_feedin_update_button_falls_back_to_live_values_when_untouched() -> None:
    _, coordinator = await _device_and_coordinator()
    button = FeedInUpdateButton(coordinator)
    _mute_state_writes(button)

    events: list[WriteEvent] = []
    coordinator.device.feed_in.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await button.async_press()
    # Nothing staged: re-writes exactly what was last read (Disabled, 4400 W).
    assert [(e.address, e.values) for e in events] == [(0x1023, [0, 44])]
    print("feedin-update-button-falls-back-to-live-values: PASSED")


async def test_active_power_control_switch_and_number_only_stage() -> None:
    _, coordinator = await _device_and_coordinator()
    switch = ActivePowerControlSwitch(coordinator)
    number = ActivePowerExportLimitNumber(coordinator)
    _mute_state_writes(switch)
    _mute_state_writes(number)
    assert switch.is_on is False  # nothing armed in the seeded register

    events: list[WriteEvent] = []
    coordinator.device.active_power_control.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await switch.async_turn_on()
    await number.async_set_native_value(30)
    assert not events, "staging must not touch the device"
    assert coordinator.pending == {
        "active_power_control_enabled": True,
        "active_power_export_limit": 30,
    }
    print("active-power-control-switch-and-number-only-stage: PASSED")


async def test_active_power_control_update_button_commits_the_staged_pair() -> None:
    _, coordinator = await _device_and_coordinator()
    coordinator.pending["active_power_control_enabled"] = True
    coordinator.pending["active_power_export_limit"] = 30
    button = ActivePowerControlUpdateButton(coordinator)
    _mute_state_writes(button)

    events: list[WriteEvent] = []
    coordinator.device.active_power_control.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await button.async_press()
    assert [(e.address, e.values) for e in events] == [(0x1105, [1, 300])]
    assert coordinator.pending == {}
    assert coordinator._refresh_calls == 1
    print("active-power-control-update-button-commits-the-staged-pair: PASSED")


async def test_a_write_failure_surfaces_as_home_assistant_error() -> None:
    _, coordinator = await _device_and_coordinator()
    coordinator.device.feed_in.modbus_unit.fail_write(0x1023, ModbusError("nope"))  # type: ignore[attr-defined]
    button = FeedInUpdateButton(coordinator)
    _mute_state_writes(button)

    try:
        await button.async_press()
    except HomeAssistantError:
        pass
    else:
        raise AssertionError("expected HomeAssistantError")
    assert coordinator.pending == {}, "nothing was staged, so nothing to clear either way"
    assert coordinator._refresh_calls == 0, "a failed write must not request a refresh"
    print("write-failure-surfaces-as-home-assistant-error: PASSED")


async def test_an_invalid_staged_value_surfaces_as_home_assistant_error() -> None:
    """feedin_max_power must be a multiple of 100 W; the library raises
    ValueError at write time, which the button must not let escape raw.
    """
    _, coordinator = await _device_and_coordinator()
    coordinator.pending["feedin_max_power"] = 3050
    button = FeedInUpdateButton(coordinator)
    _mute_state_writes(button)

    try:
        await button.async_press()
    except HomeAssistantError:
        pass
    else:
        raise AssertionError("expected HomeAssistantError")
    print("invalid-staged-value-surfaces-as-home-assistant-error: PASSED")


async def test_charger_use_mode_writes_immediately() -> None:
    _, coordinator = await _hybrid_device_and_coordinator()
    entity = ChargerUseModeSelect(coordinator)
    _mute_state_writes(entity)
    assert entity.current_option == "time_of_use"

    events: list[WriteEvent] = []
    coordinator.device.charger.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await entity.async_select_option("peak_cut_mode")
    assert [(e.address, e.values) for e in events] == [(0x1110, [int(ChargerUseMode.PEAK_CUT_MODE)])]
    assert coordinator._refresh_calls == 1
    print("charger-use-mode-writes-immediately: PASSED")


async def test_eps_mode_writes_immediately() -> None:
    _, coordinator = await _hybrid_device_and_coordinator()
    entity = EpsModeSelect(coordinator)
    _mute_state_writes(entity)
    assert entity.current_option == "turn_on_enable_cold_start"

    events: list[WriteEvent] = []
    coordinator.device.eps.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await entity.async_select_option("turn_off")
    assert [(e.address, e.values) for e in events] == [(0x1029, [0, 0])]
    assert coordinator._refresh_calls == 1
    print("eps-mode-writes-immediately: PASSED")


async def test_passive_timeout_select_and_number_only_stage() -> None:
    _, coordinator = await _hybrid_device_and_coordinator()
    action_entity = PassiveTimeoutActionSelect(coordinator)
    timeout_entity = PassiveTimeoutNumber(coordinator)
    _mute_state_writes(action_entity)
    _mute_state_writes(timeout_entity)

    events: list[WriteEvent] = []
    coordinator.device.passive.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await action_entity.async_select_option("force_standby")
    await timeout_entity.async_set_native_value(300)
    assert not events, "staging must not touch the device"
    assert coordinator.pending == {
        "passive_mode_timeout_action": PassiveModeTimeoutAction.FORCE_STANDBY,
        "passive_mode_timeout": 300,
    }
    assert action_entity.current_option == "force_standby"
    assert timeout_entity.native_value == 300
    print("passive-timeout-select-and-number-only-stage: PASSED")


async def test_passive_timeout_update_button_commits_the_staged_pair() -> None:
    _, coordinator = await _hybrid_device_and_coordinator()
    coordinator.pending["passive_mode_timeout"] = 300
    coordinator.pending["passive_mode_timeout_action"] = PassiveModeTimeoutAction.FORCE_STANDBY
    button = PassiveTimeoutUpdateButton(coordinator)
    _mute_state_writes(button)

    events: list[WriteEvent] = []
    coordinator.device.passive.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await button.async_press()
    assert [(e.address, e.values) for e in events] == [(0x1184, [300, int(PassiveModeTimeoutAction.FORCE_STANDBY)])]
    assert coordinator.pending == {}, "committed keys must be cleared"
    assert coordinator._refresh_calls == 1
    print("passive-timeout-update-button-commits-the-staged-pair: PASSED")


async def test_passive_power_numbers_only_stage() -> None:
    _, coordinator = await _hybrid_device_and_coordinator()
    grid_entity = PassiveGridPowerNumber(coordinator)
    min_entity = PassiveBatteryPowerMinNumber(coordinator)
    max_entity = PassiveBatteryPowerMaxNumber(coordinator)
    for entity in (grid_entity, min_entity, max_entity):
        _mute_state_writes(entity)

    events: list[WriteEvent] = []
    coordinator.device.passive.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await grid_entity.async_set_native_value(1000)
    await min_entity.async_set_native_value(-500)
    await max_entity.async_set_native_value(4000)
    assert not events, "staging must not touch the device"
    assert coordinator.pending == {
        "passive_mode_grid_power": 1000,
        "passive_mode_battery_power_min": -500,
        "passive_mode_battery_power_max": 4000,
    }
    print("passive-power-numbers-only-stage: PASSED")


async def test_passive_power_update_button_commits_the_staged_triple() -> None:
    _, coordinator = await _hybrid_device_and_coordinator()
    coordinator.pending["passive_mode_grid_power"] = 1000
    coordinator.pending["passive_mode_battery_power_min"] = -500
    coordinator.pending["passive_mode_battery_power_max"] = 4000
    button = PassivePowerUpdateButton(coordinator)
    _mute_state_writes(button)

    events: list[WriteEvent] = []
    coordinator.device.passive.modbus_unit.on_write(events.append)  # type: ignore[attr-defined]
    await button.async_press()
    expected_words = encode_int(1000, count=2) + encode_int(-500, count=2) + encode_int(4000, count=2)
    assert [(e.address, e.values) for e in events] == [(0x1187, expected_words)]
    assert coordinator.pending == {}, "committed keys must be cleared"
    assert coordinator._refresh_calls == 1
    print("passive-power-update-button-commits-the-staged-triple: PASSED")


async def test_a_hybrid_write_failure_surfaces_as_home_assistant_error() -> None:
    _, coordinator = await _hybrid_device_and_coordinator()
    coordinator.device.passive.modbus_unit.fail_write(0x1184, ModbusError("nope"))  # type: ignore[attr-defined]
    button = PassiveTimeoutUpdateButton(coordinator)
    _mute_state_writes(button)

    try:
        await button.async_press()
    except HomeAssistantError:
        pass
    else:
        raise AssertionError("expected HomeAssistantError")
    assert coordinator.pending == {}, "nothing was staged, so nothing to clear either way"
    assert coordinator._refresh_calls == 0, "a failed write must not request a refresh"
    print("hybrid-write-failure-surfaces-as-home-assistant-error: PASSED")


async def main() -> None:
    await test_remote_switch_writes_immediately()
    await test_feedin_select_and_number_only_stage()
    await test_feedin_update_button_commits_the_staged_pair()
    await test_feedin_update_button_falls_back_to_live_values_when_untouched()
    await test_active_power_control_switch_and_number_only_stage()
    await test_active_power_control_update_button_commits_the_staged_pair()
    await test_a_write_failure_surfaces_as_home_assistant_error()
    await test_an_invalid_staged_value_surfaces_as_home_assistant_error()
    await test_charger_use_mode_writes_immediately()
    await test_eps_mode_writes_immediately()
    await test_passive_timeout_select_and_number_only_stage()
    await test_passive_timeout_update_button_commits_the_staged_pair()
    await test_passive_power_numbers_only_stage()
    await test_passive_power_update_button_commits_the_staged_triple()
    await test_a_hybrid_write_failure_surfaces_as_home_assistant_error()
    print("ALL WRITE ENTITY TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
