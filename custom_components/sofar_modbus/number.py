"""Number platform: staged setpoints.

Each belongs to a pair (or larger group) the device only accepts as one
combined write (``feed_in`` needs its limitation mode alongside the power
ceiling; ``active_power_control`` needs its enable flag alongside the limit;
``passive`` needs its timeout alongside the timeout action, and its three
power setpoints together), so none write on their own — they stage a value in
``coordinator.pending`` and a paired button entity (``button.py``) commits the
group together.

The ``passive`` entities are HYBRID-only and have no HYBRID hardware to
verify against yet — see README's Status section.
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator
from .entity import SofarEntity


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    served = coordinator.served_components
    entities: list[NumberEntity] = []
    if "feed_in" in served:
        entities.append(FeedInMaxPowerNumber(coordinator))
    if "active_power_control" in served:
        entities.append(ActivePowerExportLimitNumber(coordinator))
    if "passive" in served:
        entities.append(PassiveTimeoutNumber(coordinator))
        entities.append(PassiveGridPowerNumber(coordinator))
        entities.append(PassiveBatteryPowerMinNumber(coordinator))
        entities.append(PassiveBatteryPowerMaxNumber(coordinator))
    async_add_entities(entities)


class FeedInMaxPowerNumber(SofarEntity, NumberEntity):
    """FeedIn: Maximum Power — staged; press FeedIn: Update to apply.

    The device wants this in 100 W steps (register 1024 is watts / 100); the
    step here matches that, but the actual multiple-of-100 check happens at
    write time in FeedInLimit.async_write_limit(), against whatever value is
    staged when the button is pressed.
    """

    _attr_translation_key = "feedin_max_power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_native_max_value = 20000
    _attr_native_step = 100
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "feedin_max_power", "feed_in")

    @property
    def native_value(self) -> float | None:
        live = self.coordinator.device.feed_in.feedin_max_power
        return self.coordinator.pending_or_live("feedin_max_power", live)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.pending["feedin_max_power"] = int(value)
        self.async_write_ha_state()


class ActivePowerExportLimitNumber(SofarEntity, NumberEntity):
    """Active Power Control: Export Limit — staged; press Update to apply."""

    _attr_translation_key = "active_power_export_limit"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "active_power_export_limit", "active_power_control")

    @property
    def native_value(self) -> float | None:
        live = self.coordinator.device.active_power_control.active_power_export_limit
        return self.coordinator.pending_or_live("active_power_export_limit", live)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.pending["active_power_export_limit"] = value
        self.async_write_ha_state()


class PassiveTimeoutNumber(SofarEntity, NumberEntity):
    """Passive: Timeout — staged; press Passive: Timeout Update to apply.

    Register 0x1184 is an unsigned 16-bit seconds count, matching the
    device's own bounds for the field.
    """

    _attr_translation_key = "passive_mode_timeout"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_native_min_value = 0
    _attr_native_max_value = 65535
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "passive_mode_timeout", "passive")

    @property
    def native_value(self) -> float | None:
        live = self.coordinator.device.passive.passive_mode_timeout
        return self.coordinator.pending_or_live("passive_mode_timeout", live)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.pending["passive_mode_timeout"] = int(value)
        self.async_write_ha_state()


class PassiveGridPowerNumber(SofarEntity, NumberEntity):
    """Passive: Desired Grid Power — staged; press Passive: Power Update to apply.

    Signed 32-bit watts (register 0x1187), like the two battery-power bounds
    below — the three go out together via ``async_write_power``.
    """

    _attr_translation_key = "passive_mode_grid_power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = -20000
    _attr_native_max_value = 20000
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "passive_mode_grid_power", "passive")

    @property
    def native_value(self) -> float | None:
        live = self.coordinator.device.passive.passive_mode_grid_power
        return self.coordinator.pending_or_live("passive_mode_grid_power", live)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.pending["passive_mode_grid_power"] = int(value)
        self.async_write_ha_state()


class PassiveBatteryPowerMinNumber(SofarEntity, NumberEntity):
    """Passive: Minimum Battery Power — staged; press Passive: Power Update to apply."""

    _attr_translation_key = "passive_mode_battery_power_min"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = -20000
    _attr_native_max_value = 20000
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "passive_mode_battery_power_min", "passive")

    @property
    def native_value(self) -> float | None:
        live = self.coordinator.device.passive.passive_mode_battery_power_min
        return self.coordinator.pending_or_live("passive_mode_battery_power_min", live)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.pending["passive_mode_battery_power_min"] = int(value)
        self.async_write_ha_state()


class PassiveBatteryPowerMaxNumber(SofarEntity, NumberEntity):
    """Passive: Maximum Battery Power — staged; press Passive: Power Update to apply."""

    _attr_translation_key = "passive_mode_battery_power_max"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = -20000
    _attr_native_max_value = 20000
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "passive_mode_battery_power_max", "passive")

    @property
    def native_value(self) -> float | None:
        live = self.coordinator.device.passive.passive_mode_battery_power_max
        return self.coordinator.pending_or_live("passive_mode_battery_power_max", live)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.pending["passive_mode_battery_power_max"] = int(value)
        self.async_write_ha_state()
