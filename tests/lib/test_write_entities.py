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
from modbus_connection.mock import MockModbusConnection, MockModbusUnit, WriteEvent  # noqa: E402
from sofar_modbus.modern import FeedinLimitationMode  # noqa: E402
from sofar_modbus.modern.device import SofarInverter  # noqa: E402

from custom_components.sofar_modbus.button import ActivePowerControlUpdateButton, FeedInUpdateButton  # noqa: E402
from custom_components.sofar_modbus.coordinator import SofarDataUpdateCoordinator  # noqa: E402
from custom_components.sofar_modbus.number import ActivePowerExportLimitNumber, FeedInMaxPowerNumber  # noqa: E402
from custom_components.sofar_modbus.select import FeedInLimitationModeSelect, RemoteSwitchSelect  # noqa: E402
from custom_components.sofar_modbus.switch import ActivePowerControlSwitch  # noqa: E402


class _FakeConnection:
    async def disconnect(self) -> None:
        pass


def _seed_serial(unit: MockModbusUnit, serial: str) -> None:
    padded = serial.ljust(14, "\x00")
    for i in range(7):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        unit.holding[0x445 + i] = (hi << 8) | lo


async def _device_and_coordinator() -> tuple[SofarInverter, SofarDataUpdateCoordinator]:
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

    coordinator = SofarDataUpdateCoordinator.__new__(SofarDataUpdateCoordinator)
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
    assert entity.current_option == "On"

    events: list[WriteEvent] = []
    coordinator.device.remote._unit.on_write(events.append)  # type: ignore[attr-defined]
    await entity.async_select_option("Off")
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
    coordinator.device.feed_in._unit.on_write(events.append)  # type: ignore[attr-defined]
    await mode_entity.async_select_option("Enabled - Feed-in limitation")
    await power_entity.async_set_native_value(3000)
    assert not events, "staging must not touch the device"
    assert coordinator.pending == {
        "feedin_limitation_mode": FeedinLimitationMode.ENABLED_FEED_IN_LIMITATION,
        "feedin_max_power": 3000,
    }
    assert mode_entity.current_option == "Enabled - Feed-in limitation"
    assert power_entity.native_value == 3000
    print("feedin-select-and-number-only-stage: PASSED")


async def test_feedin_update_button_commits_the_staged_pair() -> None:
    _, coordinator = await _device_and_coordinator()
    coordinator.pending["feedin_limitation_mode"] = FeedinLimitationMode.ENABLED_FEED_IN_LIMITATION
    coordinator.pending["feedin_max_power"] = 3000
    button = FeedInUpdateButton(coordinator)
    _mute_state_writes(button)

    events: list[WriteEvent] = []
    coordinator.device.feed_in._unit.on_write(events.append)  # type: ignore[attr-defined]
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
    coordinator.device.feed_in._unit.on_write(events.append)  # type: ignore[attr-defined]
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
    coordinator.device.active_power_control._unit.on_write(events.append)  # type: ignore[attr-defined]
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
    coordinator.device.active_power_control._unit.on_write(events.append)  # type: ignore[attr-defined]
    await button.async_press()
    assert [(e.address, e.values) for e in events] == [(0x1105, [1, 300])]
    assert coordinator.pending == {}
    assert coordinator._refresh_calls == 1
    print("active-power-control-update-button-commits-the-staged-pair: PASSED")


async def test_a_write_failure_surfaces_as_home_assistant_error() -> None:
    _, coordinator = await _device_and_coordinator()
    coordinator.device.feed_in._unit.fail_write(0x1023, ModbusError("nope"))  # type: ignore[attr-defined]
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


async def main() -> None:
    await test_remote_switch_writes_immediately()
    await test_feedin_select_and_number_only_stage()
    await test_feedin_update_button_commits_the_staged_pair()
    await test_feedin_update_button_falls_back_to_live_values_when_untouched()
    await test_active_power_control_switch_and_number_only_stage()
    await test_active_power_control_update_button_commits_the_staged_pair()
    await test_a_write_failure_surfaces_as_home_assistant_error()
    await test_an_invalid_staged_value_surfaces_as_home_assistant_error()
    print("ALL WRITE ENTITY TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
