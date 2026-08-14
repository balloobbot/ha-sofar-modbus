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
from pathlib import Path

# coordinator.py uses package-relative imports (.const, .generated_sensors), so
# unlike generated_sensors.py it can't be loaded as a bare top-level module —
# import it as part of custom_components.sofar_modbus instead. custom_components
# has no __init__.py, but Python 3's implicit namespace packages make that fine.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: E402
from modbus_connection import ModbusConnectionError, ModbusTimeoutError  # noqa: E402
from modbus_connection.mock import MockModbusConnection, MockModbusUnit  # noqa: E402
from sofar_modbus.modern.device import SofarInverter  # noqa: E402

from custom_components.sofar_modbus.coordinator import SofarDataUpdateCoordinator  # noqa: E402


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
    coordinator = _coordinator(device, _FakeConnection())
    await coordinator._async_update_data()

    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    report = await coordinator._async_update_data()
    assert "grid" in report.failed
    assert "state" in report.updated, "a different fast-tier component must not be affected"
    assert coordinator._consecutive_failures["grid"] == 1

    report = await coordinator._async_update_data()
    assert coordinator._consecutive_failures["grid"] == 2
    print("failure-survives-retry-is-tracked: PASSED")


async def test_disconnects_after_repeated_timeouts() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    connection = _FakeConnection()
    coordinator = _coordinator(device, connection)
    await coordinator._async_update_data()

    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    for _ in range(3):
        await coordinator._async_update_data()
    assert connection.disconnect_calls == 1, "should disconnect exactly once at the threshold"
    assert coordinator._consecutive_timeouts == 0, "counter resets after disconnecting"
    print("disconnects-after-repeated-timeouts: PASSED")


async def test_slow_tier_is_skipped_on_off_cycles() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())
    await coordinator._async_update_data()  # settles tiers

    for _ in range(3):  # cycles not due (N=4)
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
    try:
        await coordinator._async_update_data()
    except UpdateFailed as err:
        assert "no component answered" in str(err)
    else:
        raise AssertionError("expected UpdateFailed when all components time out")
    print("all-timeout-outage-raises-update-failed: PASSED")


async def test_force_slow_tier_polls_slow_tier_on_off_cycles() -> None:
    unit = MockModbusConnection().for_unit(1)
    device = _device(unit)
    coordinator = _coordinator(device, _FakeConnection())
    await coordinator._async_update_data()  # settles tiers, cycle 0 done (next cycle is 1, not due)

    # Next cycle is off-cycle (cycle 1, N=4)
    coordinator._force_slow_tier = True
    report = await coordinator._async_update_data()
    assert "energy" in report.updated, "slow tier should poll when forced"
    assert not coordinator._force_slow_tier, "force flag should reset after the poll"

    # Cycle 2 without force should skip slow tier
    report = await coordinator._async_update_data()
    assert "energy" not in report.updated, "slow tier should be skipped again when not forced"
    print("force-slow-tier-polls-slow-tier-on-off-cycles: PASSED")


async def main() -> None:
    await test_retry_recovers_a_transient_failure()
    await test_a_failure_that_survives_retry_is_tracked_and_leaves_others_alone()
    await test_disconnects_after_repeated_timeouts()
    await test_slow_tier_is_skipped_on_off_cycles()
    await test_force_slow_tier_polls_slow_tier_on_off_cycles()
    await test_a_dead_link_raises_update_failed()
    await test_all_timeout_outage_raises_update_failed_and_skips_retry()
    print("ALL COORDINATOR TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
