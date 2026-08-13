"""Number platform: two staged setpoints.

Both belong to a pair the device only accepts as one combined write
(``feed_in`` needs its limitation mode alongside the power ceiling;
``active_power_control`` needs its enable flag alongside the limit), so
neither writes on its own — they stage a value in ``coordinator.pending`` and
a paired button entity (``button.py``) commits the pair together.
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator
from .entity import SofarEntity


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    served = coordinator.data.updated | set(coordinator.data.failed)
    entities: list[NumberEntity] = []
    if "feed_in" in served:
        entities.append(FeedInMaxPowerNumber(coordinator))
    if "active_power_control" in served:
        entities.append(ActivePowerExportLimitNumber(coordinator))
    async_add_entities(entities)


class FeedInMaxPowerNumber(SofarEntity, NumberEntity):
    """FeedIn: Maximum Power — staged; press FeedIn: Update to apply.

    The device wants this in 100 W steps (register 1024 is watts / 100); the
    step here matches that, but the actual multiple-of-100 check happens at
    write time in FeedInLimit.async_write_limit(), against whatever value is
    staged when the button is pressed.
    """

    _attr_name = "FeedIn: Maximum Power"
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

    _attr_name = "Active Power Control: Export Limit"
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
