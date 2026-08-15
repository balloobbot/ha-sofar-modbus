"""Tests for the Sofar Modbus sensor platform."""

from __future__ import annotations

from collections import deque
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.sensor import SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sofar_modbus.const import CONF_MODBUS_ADDR, CONF_READ_EPS, DOMAIN
from custom_components.sofar_modbus.coordinator import _HEALTH_WINDOW, SofarDataUpdateCoordinator
from custom_components.sofar_modbus.sensor import (
    SENSOR_DESCRIPTIONS,
    SofarSensor,
    SofarSensorDescription,
    SofarTotalSensor,
)

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
    unit.holding[0x0404] = 2  # Running (enum State)
    unit.holding[0x0484] = 5000  # 50.00 Hz (grid_frequency)
    unit.holding[0x0684] = 0  # solar_generation_today high word
    unit.holding[0x0685] = 1000  # solar_generation_today low word (1000 * 0.01 = 10.0 kWh)
    unit.holding[0x068A] = 0  # load_consumption_total high word
    unit.holding[0x068B] = 12000  # load_consumption_total low word -> 1200.0 kWh


async def test_sensor_entities_created_and_state(hass: HomeAssistant) -> None:
    """Test sensor entities are created in entity registry with correct states."""
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
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    # Check a measurement sensor (grid_frequency)
    grid_freq_entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "SS2ES104N5S445_grid_frequency")
    assert grid_freq_entity_id is not None
    state = hass.states.get(grid_freq_entity_id)
    assert state is not None
    assert float(state.state) == 50.0

    # Check an enum sensor (state -> Running -> Grid Connected)
    inverter_state_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "SS2ES104N5S445_system_state")
    assert inverter_state_id is not None
    state = hass.states.get(inverter_state_id)
    assert state is not None
    assert state.state == "Grid Connected"

    # Check total increasing sensor (solar_generation_today)
    gen_today_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "SS2ES104N5S445_solar_generation_today")
    assert gen_today_id is not None
    state = hass.states.get(gen_today_id)
    assert state is not None
    assert float(state.state) == 10.0  # 100 * 0.1


async def test_sensor_availability_on_component_failure(hass: HomeAssistant) -> None:
    """Test that measurement sensor becomes unavailable when component fails, but total holds available."""
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
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    grid_freq_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "SS2ES104N5S445_grid_frequency")
    gen_today_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "SS2ES104N5S445_solar_generation_today")
    assert grid_freq_id is not None
    assert gen_today_id is not None

    # Fail grid reads (register 0x0484)
    unit.fail_read(0x0484, ModbusTimeoutError("Timeout reading grid"))

    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Measurement sensor on failed component becomes unavailable
    grid_state = hass.states.get(grid_freq_id)
    assert grid_state is not None
    assert grid_state.state == "unavailable"

    # Total sensor holds available
    gen_state = hass.states.get(gen_today_id)
    assert gen_state is not None
    assert gen_state.state != "unavailable"


async def test_communication_health_sensor(hass: HomeAssistant) -> None:
    """Test the communication_health sensor's state and attributes track poll outcomes."""
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
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    health_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "SS2ES104N5S445_communication_health")
    assert health_id is not None

    # Every poll during setup was clean (setup schedules its own background
    # refreshes — see __init__.py's _async_startup_refresh — so more than one
    # cycle may already have landed; only the *rate*, not the cycle count, is
    # deterministic here).
    state = hass.states.get(health_id)
    assert state is not None
    assert state.state == "Good"
    assert state.attributes["success_rate"] == 100.0
    assert state.attributes["last_error"] is None
    assert state.attributes["last_error_time"] is None

    # A failed poll degrades the state and populates the error attributes.
    unit.fail_read(0x0484, ModbusTimeoutError("Timeout reading grid"))
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(health_id)
    assert state is not None
    assert state.state != "Good"
    assert state.attributes["success_rate"] == coordinator.success_rate
    assert coordinator.success_rate is not None and coordinator.success_rate < 100.0
    assert state.attributes["last_error"] is not None
    assert "ModbusTimeoutError" in state.attributes["last_error"]
    assert state.attributes["last_error_time"] is not None


async def test_total_sensor_restore_data_parsing(hass: HomeAssistant) -> None:
    """Test SofarTotalSensor restore data parsing including valid, invalid, and None values."""
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
        await hass.async_block_till_done()

    coord = entry.runtime_data
    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "load_consumption_total")

    # Valid numeric restoration before poll (live value is None)
    coord.device.energy.load_consumption_total = None  # type: ignore[assignment]
    sensor = SofarTotalSensor(coord, desc)
    sensor.hass = hass
    sensor.async_get_last_sensor_data = AsyncMock(return_value=SimpleNamespace(native_value="555.5"))  # type: ignore[method-assign]
    await sensor.async_added_to_hass()
    assert sensor.native_value == 555.5
    assert sensor._total_increasing_high_water == 555.5

    # A torn read dip after restart is held against the restored high water mark
    assert sensor._smoothed_total_increasing(555.4) == 555.5

    # Invalid non-numeric restoration gracefully handled
    sensor_invalid = SofarTotalSensor(coord, desc)
    sensor_invalid.hass = hass
    sensor_invalid.async_get_last_sensor_data = AsyncMock(return_value=SimpleNamespace(native_value="not_a_number"))  # type: ignore[method-assign]
    await sensor_invalid.async_added_to_hass()
    assert sensor_invalid._total_increasing_high_water is None

    # TOTAL (not TOTAL_INCREASING) state class
    coord.device.energy.load_consumption_total = 120.0  # type: ignore[assignment]
    total_desc = SofarSensorDescription(
        key="load_consumption_total",
        component="energy",
        name="Test Total",
        state_class=SensorStateClass.TOTAL,
    )
    total_sensor = SofarTotalSensor(coord, total_desc)
    assert total_sensor.native_value == 120.0


async def test_smoothed_total_increasing_dip_tolerance(hass: HomeAssistant) -> None:
    """Test that small dips in total increasing sensors are ignored while large drops pass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SS2ES104N5S445",
        data=MOCK_CONFIG,
    )

    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(1)
    _seed_pv_inverter(unit)

    entry.add_to_hass(hass)

    with patch("custom_components.sofar_modbus.build_connection", return_value=mock_conn):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coord = entry.runtime_data
    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "load_consumption_total")
    sensor = SofarTotalSensor(coord, desc)
    sensor._attr_native_value = 1000.0
    sensor._total_increasing_high_water = 1000.0

    # Small dip: 999.9 (0.01% dip) -> held at 1000.0
    assert sensor._smoothed_total_increasing(999.9) == 1000.0

    # Increase: 1005.0 -> advances to 1005.0
    assert sensor._smoothed_total_increasing(1005.0) == 1005.0
    assert sensor._total_increasing_high_water == 1005.0

    # Large drop: 10.0 (midnight reset / meter reset) -> passes through
    assert sensor._smoothed_total_increasing(10.0) == 10.0
    assert sensor._total_increasing_high_water == 10.0


async def test_sensor_dead_link_unavailable(hass: HomeAssistant) -> None:
    """Test that SofarSensor returns False when coordinator last_update_success is False."""
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
        await hass.async_block_till_done()

    coord = entry.runtime_data
    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "grid_frequency")
    sensor = SofarSensor(coord, desc)
    coord.last_update_success = False
    assert not sensor.available


def test_coordinator_served_components_fallbacks() -> None:
    """Test coordinator.served_components fallback branches when device._polled is None."""
    from sofar_modbus.model import UpdateReport

    coord = SofarDataUpdateCoordinator.__new__(SofarDataUpdateCoordinator)
    coord.device = SimpleNamespace(_polled=None)  # type: ignore[assignment]
    coord.data = None  # type: ignore[assignment]
    assert coord.served_components == frozenset()

    coord.data = UpdateReport(updated={"grid"}, failed={"energy": ModbusTimeoutError("stuck")})
    assert coord.served_components == frozenset({"grid", "energy"})


async def test_coordinator_all_components_failed_exception_group() -> None:
    """Test coordinator raises UpdateFailed with ExceptionGroup when multiple components fail."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    coord = SofarDataUpdateCoordinator.__new__(SofarDataUpdateCoordinator)
    coord.name = "test"
    coord._fast = {"c1": SimpleNamespace(), "c2": SimpleNamespace()}  # type: ignore[assignment,dict-item]
    coord._slow = {}
    coord._force_slow_tier = False
    coord._cycle = 0
    coord._consecutive_timeouts = 0
    coord._consecutive_failures = {}
    coord._poll_outcomes = deque(maxlen=_HEALTH_WINDOW)
    coord.last_error = None
    coord.last_error_time = None

    from sofar_modbus.model import UpdateReport

    failed_report = UpdateReport(
        updated=set(),
        failed={
            "c1": ModbusTimeoutError("err1"),
            "c2": ModbusTimeoutError("err2"),
        },
    )

    coord._poll = AsyncMock(return_value=failed_report)  # type: ignore[method-assign]
    coord._retry_failed = AsyncMock(return_value=failed_report)  # type: ignore[method-assign]

    # 1. Multiple errors -> ExceptionGroup
    with pytest.raises(UpdateFailed) as exc_info:
        await coord._async_update_data()
    assert "no component answered" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, ExceptionGroup)

    # 3. Empty report (no updated and no failed)
    empty_report = UpdateReport(updated=set(), failed={})
    coord._poll = AsyncMock(return_value=empty_report)  # type: ignore[method-assign]
    coord._retry_failed = AsyncMock(return_value=empty_report)  # type: ignore[method-assign]
    with pytest.raises(UpdateFailed) as exc_info_empty:
        await coord._async_update_data()
    assert "no component answered" in str(exc_info_empty.value)
