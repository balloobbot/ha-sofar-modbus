"""Standalone script: the diagnostics payload against the mock backend — no
real Home Assistant required. Safe to run standalone:
`python tests/lib/test_diagnostics.py`.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modbus_connection import ModbusTimeoutError  # noqa: E402
from modbus_connection.mock import MockModbusConnection, MockModbusUnit  # noqa: E402
from sofar_modbus.modern.device import SofarInverter  # noqa: E402

from custom_components.sofar_modbus.coordinator import SofarDataUpdateCoordinator  # noqa: E402
from custom_components.sofar_modbus.diagnostics import async_get_config_entry_diagnostics  # noqa: E402


class _FakeConnection:
    async def disconnect(self) -> None:
        pass


class _FakeEntry:
    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        self.runtime_data = coordinator


def _seed_serial(unit: MockModbusUnit, serial: str) -> None:
    padded = serial.ljust(14, "\x00")
    for i in range(7):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        unit.holding[0x445 + i] = (hi << 8) | lo


def _coordinator(device: SofarInverter) -> SofarDataUpdateCoordinator:
    coordinator = SofarDataUpdateCoordinator.__new__(SofarDataUpdateCoordinator)
    coordinator.name = "test"
    coordinator.connection = _FakeConnection()  # type: ignore[assignment]
    coordinator.device = device
    coordinator._consecutive_timeouts = 0
    coordinator._consecutive_failures = {}
    coordinator._cycle = 0
    coordinator._fast = None
    coordinator._slow = None
    coordinator._force_slow_tier = False
    coordinator.data = None  # type: ignore[assignment]
    return coordinator


async def test_diagnostics_dumps_raw_registers_for_every_served_component() -> None:
    unit = MockModbusConnection().for_unit(1)
    _seed_serial(unit, "SP1XXES100XX")
    unit.holding[0x0404] = 2  # state
    unit.holding[0x0484] = 5000  # grid
    unit.holding[0x0684] = 100  # energy

    device = SofarInverter(unit)
    coordinator = _coordinator(device)
    coordinator.data = await coordinator._async_update_data()

    diagnostics = await async_get_config_entry_diagnostics(None, _FakeEntry(coordinator))  # type: ignore[arg-type]

    assert diagnostics["model"] == device.model
    assert diagnostics["serial_number"] == device.serial_number
    assert "grid" in diagnostics["served_components"]
    assert "energy" in diagnostics["served_components"]
    assert diagnostics["read_errors"] == {}
    assert "holding" in diagnostics["registers"]
    assert diagnostics["registers"]["holding"][0x0484] == 5000
    assert diagnostics["registers"]["holding"][0x0684] == 100
    print("diagnostics-dumps-raw-registers: PASSED")


async def test_a_failed_component_is_reported_not_fatal() -> None:
    unit = MockModbusConnection().for_unit(1)
    _seed_serial(unit, "SP1XXES100XX")
    unit.holding[0x0404] = 2
    unit.holding[0x0484] = 5000
    unit.holding[0x0684] = 100

    device = SofarInverter(unit)
    coordinator = _coordinator(device)
    coordinator.data = await coordinator._async_update_data()

    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    diagnostics = await async_get_config_entry_diagnostics(None, _FakeEntry(coordinator))  # type: ignore[arg-type]

    assert "device" in diagnostics["read_errors"]
    assert diagnostics["registers"] == {}
    print("failed-component-reported-not-fatal: PASSED")


async def main() -> None:
    await test_diagnostics_dumps_raw_registers_for_every_served_component()
    await test_a_failed_component_is_reported_not_fatal()
    print("ALL DIAGNOSTICS TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
