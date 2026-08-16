"""Standalone script: SofarDataUpdateCoordinator's retry and tiered-cadence
logic, against the mock backend — no real Home Assistant required.

Built via __new__, bypassing DataUpdateCoordinator.__init__ (which needs a
real hass/ConfigEntry) — only the attributes _async_update_data() and its
helpers actually touch are set, the same pattern test_smoke.py already uses
for a bare SofarInverter. Safe to run standalone:
`python tests/lib/test_coordinator.py`.
"""

from __future__ import annotations

import asyncio
import sys
from collections import deque
from pathlib import Path

# coordinator.py uses package-relative imports (.const, .generated_sensors), so
# unlike generated_sensors.py it can't be loaded as a bare top-level module —
# import it as part of custom_components.sofar_modbus instead. custom_components
# has no __init__.py, but Python 3's implicit namespace packages make that fine.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: E402
from modbus_connection import IllegalDataAddressError, ModbusConnectionError, ModbusTimeoutError  # noqa: E402
from modbus_connection.mock import MockModbusConnection, MockModbusUnit  # noqa: E402
from sofar_modbus.modern.device import SofarInverter  # noqa: E402

from custom_components.sofar_modbus.coordinator import (  # noqa: E402
    _HEALTH_WINDOW,
    _SLOW_TIER_EVERY_N_CYCLES,
    SofarDataUpdateCoordinator,
)


class _FakeConnection:
    """Stands in for the real ModbusConnection; only disconnect() is called."""

    def __init__(self) -> None:
        self.disconnect_calls = 0

    async def disconnect(self) -> None:
        self.disconnect_calls += 1


def _seed_serial(unit: MockModbusUnit, serial: str) -> None:
    padded = serial.ljust(14, "\x00")
    for i in range(7):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        unit.holding[0x445 + i] = (hi << 8) | lo


def _coordinator(device: SofarInverter, connection: _FakeConnection) -> SofarDataUpdateCoordinator:
    coordinator = SofarDataUpdateCoordinator.__new__(SofarDataUpdateCoordinator)
    coordinator.name = "test"
    coordinator.connection = connection  # type: ignore[assignment]
    coordinator.device = device
    coordinator._consecutive_timeouts = 0
    coordinator._consecutive_failures = {}
    coordinator._poll_outcomes = deque(maxlen=_HEALTH_WINDOW)
    coordinator.last_error = None
    coordinator.last_error_time = None
    coordinator._cycle = 0
    coordinator._fast = None
    coordinator._slow = None
    coordinator._force_slow_tier = False
    return coordinator


def _device(unit: MockModbusUnit) -> SofarInverter:
    _seed_serial(unit, "SP1XXES100XX")  # HYBRID: grid (fast) + energy (slow) both served
    unit.holding[0x0404] = 2  # system_state, in `state` (fast tier)
    unit.holding[0x0484] = 5000  # grid_frequency, in `grid` (fast tier)
    unit.holding[0x0684] = 100  # solar_generation_today, in `energy` (slow tier)
    return SofarInverter(unit)


async def test_retry_recovers_a_transient_failure() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())

    report = await coordinator._async_update_data()
    assert report.complete, f"first poll should be clean against the mock: {report.failed}"
    assert coordinator._fast is not None and "grid" in coordinator._fast
    assert coordinator._slow is not None and "energy" in coordinator._slow
    assert "feed_in" in coordinator._slow
    assert "remote" in coordinator._slow

    unit.fail_read(0x0484, ModbusTimeoutError("transient"))
    first_attempt = await coordinator._poll(coordinator._fast)
    assert "grid" in first_attempt.failed, "expected the first attempt to fail"

    unit.fail_read(0x0484, None)  # the glitch clears before the retry
    retried = await coordinator._retry_failed(first_attempt)
    assert retried.complete, f"retry should have recovered: {retried.failed}"
    assert "grid" in retried.updated
    assert "grid" not in coordinator._consecutive_failures
    print("retry-recovers-a-transient-failure: PASSED")


async def test_a_failure_that_survives_retry_is_tracked_and_leaves_others_alone() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    connection = _FakeConnection()
    coordinator = _coordinator(device, connection)
    await coordinator._async_update_data()

    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    report = await coordinator._async_update_data()
    assert "grid" in report.failed
    assert "state" in report.updated, "a different fast-tier component must not be affected"
    assert coordinator._consecutive_failures["grid"] == 1
    assert coordinator._consecutive_timeouts == 0, "partial timeout does not count as a link timeout"

    report = await coordinator._async_update_data()
    assert coordinator._consecutive_failures["grid"] == 2
    assert coordinator._consecutive_timeouts == 0
    assert connection.disconnect_calls == 0, "should not disconnect for partial timeouts"
    print("failure-survives-retry-is-tracked: PASSED")


async def test_success_rate_reflects_mixed_outcomes() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())

    await coordinator._async_update_data()  # cycle 1: clean, also settles tiers
    assert coordinator.success_rate == 100.0

    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    await coordinator._async_update_data()  # cycle 2: grid fails
    unit.fail_read(0x0484, None)
    await coordinator._async_update_data()  # cycle 3: recovered

    assert list(coordinator._poll_outcomes) == [True, False, True]
    assert coordinator.success_rate == round(100 * 2 / 3, 1)
    print("success-rate-reflects-mixed-outcomes: PASSED")


async def test_health_window_caps_and_drops_oldest_outcome() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())

    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    report = await coordinator._async_update_data()  # cycle 1: the one failure, also settles tiers
    assert "grid" in report.failed
    unit.fail_read(0x0484, None)
    for _ in range(_HEALTH_WINDOW - 1):  # cycles 2..N: recovered
        await coordinator._async_update_data()
    assert len(coordinator._poll_outcomes) == _HEALTH_WINDOW, "window fills to its cap"
    assert coordinator.success_rate == round(100 * (_HEALTH_WINDOW - 1) / _HEALTH_WINDOW, 1)

    await coordinator._async_update_data()  # cycle N+1: one more success, evicting the oldest (failed) outcome
    assert len(coordinator._poll_outcomes) == _HEALTH_WINDOW, "window stays capped, not unbounded"
    assert coordinator.success_rate == 100.0, "the oldest (failed) outcome should have been evicted"
    print("health-window-caps-and-drops-oldest: PASSED")


async def test_last_error_is_recorded_and_not_cleared_by_a_later_success() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())
    await coordinator._async_update_data()  # settle tiers, clean
    assert coordinator.last_error is None
    assert coordinator.last_error_time is None

    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    await coordinator._async_update_data()
    assert coordinator.last_error is not None and "ModbusTimeoutError" in coordinator.last_error
    recorded_at = coordinator.last_error_time
    assert recorded_at is not None

    unit.fail_read(0x0484, None)
    report = await coordinator._async_update_data()
    assert report.complete
    assert coordinator.last_error is not None, "last_error means 'most recent problem', not 'current problem'"
    assert coordinator.last_error_time == recorded_at, "an unrelated success must not clear or refresh it"
    print("last-error-is-recorded-and-not-cleared: PASSED")


async def test_disconnects_after_repeated_timeouts() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    connection = _FakeConnection()
    coordinator = _coordinator(device, connection)
    await coordinator._async_update_data()

    unit.fail_requests(ModbusTimeoutError("stuck"))
    for _ in range(3):
        try:
            await coordinator._async_update_data()
        except UpdateFailed:
            pass
        else:
            raise AssertionError("expected UpdateFailed on fatal timeout")
    assert connection.disconnect_calls == 1, "should disconnect exactly once at the threshold"
    assert coordinator._consecutive_timeouts == 0, "counter resets after disconnecting"
    print("disconnects-after-repeated-timeouts: PASSED")


async def test_consecutive_timeouts_resets_on_successful_poll() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    connection = _FakeConnection()
    coordinator = _coordinator(device, connection)
    await coordinator._async_update_data()

    unit.fail_requests(ModbusTimeoutError("stuck"))
    for _ in range(2):
        try:
            await coordinator._async_update_data()
        except UpdateFailed:
            pass
        else:
            raise AssertionError("expected UpdateFailed on fatal timeout")
    assert coordinator._consecutive_timeouts == 2
    assert connection.disconnect_calls == 0

    # Device recovers before reaching the disconnect threshold
    unit.fail_requests(None)
    report = await coordinator._async_update_data()
    assert report.complete
    assert coordinator._consecutive_timeouts == 0, "counter should reset on recovery"
    assert connection.disconnect_calls == 0
    print("consecutive-timeouts-resets-on-successful-poll: PASSED")


async def test_slow_tier_is_skipped_on_off_cycles() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())
    await coordinator._async_update_data()  # settles tiers

    for _ in range(_SLOW_TIER_EVERY_N_CYCLES - 1):  # cycles not due
        report = await coordinator._async_update_data()
        assert "energy" not in report.updated, "slow tier should be skipped off-cycle"
        assert "grid" in report.updated

    report = await coordinator._async_update_data()  # due cycle
    assert "energy" in report.updated, "slow tier should poll on its due cycle"
    print("slow-tier-skipped-on-off-cycles: PASSED")


async def test_a_dead_link_raises_update_failed() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())
    await coordinator._async_update_data()

    unit.fail_requests(ModbusConnectionError("link down"))
    try:
        await coordinator._async_update_data()
    except UpdateFailed:
        pass
    else:
        raise AssertionError("expected UpdateFailed for a dead link")
    print("dead-link-raises-update-failed: PASSED")


async def test_all_timeout_outage_raises_update_failed_and_skips_retry() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())
    await coordinator._async_update_data()

    unit.fail_requests(ModbusTimeoutError("stuck"))
    unit.read_events.clear()
    try:
        await coordinator._async_update_data()
    except UpdateFailed as err:
        assert "stuck" in str(err)
    else:
        raise AssertionError("expected UpdateFailed when all components time out")

    # Fast-fail: the poll gives up on the first component timeout rather than
    # walking through the remaining components paying a timeout for each.
    assert len(unit.read_events) == 1
    print("all-timeout-outage-raises-update-failed: PASSED")


async def test_refusal_on_first_component_is_contained() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())
    await coordinator._async_update_data()

    # If first component fails with an exception response (e.g. IllegalDataAddressError),
    # proving the device is awake, subsequent component reads proceed and are contained.
    assert coordinator._fast is not None
    first_component_name, first_component = next(iter(coordinator._fast.items()))
    first_field = next(f for f in type(first_component).declared_fields.values() if getattr(f, "address", None) is not None)
    unit.fail_read(first_field.address, IllegalDataAddressError())
    report = await coordinator._poll(coordinator._fast)
    assert first_component_name in report.failed
    assert len(report.updated) > 0
    print("refusal-on-first-component-is-contained: PASSED")


async def test_force_slow_tier_polls_slow_tier_on_off_cycles() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())
    await coordinator._async_update_data()  # settles tiers, cycle 0 done (next cycle is 1, not due)

    # Next cycle is off-cycle (cycle 1)
    coordinator._force_slow_tier = True
    report = await coordinator._async_update_data()
    assert "energy" in report.updated, "slow tier should poll when forced"
    assert not coordinator._force_slow_tier, "force flag should reset after the poll"

    # Cycle 2 without force should skip slow tier
    report = await coordinator._async_update_data()
    assert "energy" not in report.updated, "slow tier should be skipped again when not forced"
    print("force-slow-tier-polls-slow-tier-on-off-cycles: PASSED")


async def test_first_poll_only_polls_fast_tier_and_exposes_all_served_components() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())

    # Cycle 0 (startup): Fast tier polled immediately
    report = await coordinator._async_update_data()
    assert report.complete
    assert "grid" in report.updated
    assert "state" in report.updated
    assert "identity" not in report.updated
    assert "energy" not in report.updated
    assert "grid" in coordinator.served_components
    assert "energy" in coordinator.served_components
    assert "feed_in" in coordinator.served_components

    # Background slow tier refresh
    coordinator._force_slow_tier = True
    report = await coordinator._async_update_data()
    assert "energy" in report.updated
    print("first-poll-only-polls-fast-tier: PASSED")


async def test_pre_identified_device_initializes_tiers_in_memory() -> None:
    from sofar_modbus.modern.device import identify

    unit = MockModbusConnection().for_unit(1)
    # Note: no serial seeded in holding registers!
    serial = "SP1XXES100XX"
    inverter_type, model = identify(serial)
    device = SofarInverter(unit, inverter_type=inverter_type)
    assert device.inverter_type is not None
    device.prime(serial, model)

    # Seed fast tier registers
    unit.holding[0x0404] = 2
    unit.holding[0x0484] = 5000

    coordinator = SofarDataUpdateCoordinator.__new__(SofarDataUpdateCoordinator)
    coordinator.name = "test"
    coordinator.connection = _FakeConnection()  # type: ignore[assignment]
    coordinator.device = device
    coordinator._consecutive_timeouts = 0
    coordinator._consecutive_failures = {}
    coordinator._poll_outcomes = deque(maxlen=_HEALTH_WINDOW)
    coordinator.last_error = None
    coordinator.last_error_time = None
    coordinator._cycle = 0
    coordinator._force_slow_tier = False
    # Coordinator __init__ logic
    from custom_components.sofar_modbus.coordinator import _volatile_components

    volatile = _volatile_components()
    assert device.polled_components is not None
    coordinator._fast = {name: getattr(device, name) for name in device.polled_components if name in volatile}
    coordinator._slow = {name: getattr(device, name) for name in device.polled_components if name not in volatile}

    assert "grid" in coordinator.served_components
    assert "energy" in coordinator.served_components
    assert "feed_in" in coordinator.served_components

    # First update polls fast tier without ever reading serial register 0x0445
    report = await coordinator._async_update_data()
    assert report.complete
    assert "grid" in report.updated
    assert "state" in report.updated
    assert 0x0445 not in [e.address for e in unit.read_events]
    print("pre-identified-device-initializes-tiers-in-memory: PASSED")


def test_offgrid_output_components_are_volatile() -> None:
    """Regression guard for issue #46: an omitted state_class on a sensor
    description silently opts its whole component out of the fast poll tier.
    offgrid_single_phase/offgrid_three_phase are live electrical output and
    must land in _volatile_components()'s fast tier.
    """
    from custom_components.sofar_modbus.coordinator import _volatile_components

    volatile = _volatile_components()
    assert "offgrid_single_phase" in volatile
    assert "offgrid_three_phase" in volatile
    print("offgrid-output-components-are-volatile: PASSED")


def test_volatile_components_matches_sensor_state_class_metadata() -> None:
    """coordinator.py's _VOLATILE_COMPONENTS is hand-maintained, not derived
    from sensor.py (so the coordinator has no import-time dependency on any
    platform module — see coordinator.py's module docstring). This guards
    against the two drifting apart: a new MEASUREMENT sensor row on a
    component missing from _VOLATILE_COMPONENTS would silently land it in
    the slow tier.
    """
    from homeassistant.components.sensor import SensorStateClass

    from custom_components.sofar_modbus.coordinator import _volatile_components
    from custom_components.sofar_modbus.sensor import SENSOR_DESCRIPTIONS

    from_sensor_metadata = frozenset(
        description.component for description in SENSOR_DESCRIPTIONS if description.state_class == SensorStateClass.MEASUREMENT
    )
    assert _volatile_components() == from_sensor_metadata
    print("volatile-components-matches-sensor-state-class-metadata: PASSED")


async def main() -> None:
    await test_retry_recovers_a_transient_failure()
    await test_a_failure_that_survives_retry_is_tracked_and_leaves_others_alone()
    await test_success_rate_reflects_mixed_outcomes()
    await test_health_window_caps_and_drops_oldest_outcome()
    await test_last_error_is_recorded_and_not_cleared_by_a_later_success()
    await test_disconnects_after_repeated_timeouts()
    await test_consecutive_timeouts_resets_on_successful_poll()
    await test_slow_tier_is_skipped_on_off_cycles()
    await test_force_slow_tier_polls_slow_tier_on_off_cycles()
    await test_a_dead_link_raises_update_failed()
    await test_all_timeout_outage_raises_update_failed_and_skips_retry()
    await test_refusal_on_first_component_is_contained()
    await test_first_poll_only_polls_fast_tier_and_exposes_all_served_components()
    await test_pre_identified_device_initializes_tiers_in_memory()
    test_offgrid_output_components_are_volatile()
    test_volatile_components_matches_sensor_state_class_metadata()
    print("ALL COORDINATOR TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
