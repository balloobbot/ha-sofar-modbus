"""Button platform: commits the staged writes select/number/switch can't
issue on their own — the device only accepts these as one combined write.

Each button resolves the pair's current value (staged if the user touched it
this session, otherwise the last live read — coordinator.pending_or_live()),
performs the one write, clears the keys it just committed, and requests a
refresh so the next poll confirms what actually landed.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from modbus_connection import ModbusError

from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator
from .entity import SofarEntity
from .switch import resolve_active_power_control_enabled


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    served = coordinator.data.updated | set(coordinator.data.failed)
    entities: list[ButtonEntity] = []
    if "feed_in" in served:
        entities.append(FeedInUpdateButton(coordinator))
    if "active_power_control" in served:
        entities.append(ActivePowerControlUpdateButton(coordinator))
    async_add_entities(entities)


class FeedInUpdateButton(SofarEntity, ButtonEntity):
    """FeedIn: Update — writes the staged (or last-read) mode and power together."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "FeedIn: Update"

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "feedin_update", "feed_in")

    async def async_press(self) -> None:
        feed_in = self.coordinator.device.feed_in
        mode = self.coordinator.pending_or_live("feedin_limitation_mode", feed_in.feedin_limitation_mode)
        power = self.coordinator.pending_or_live("feedin_max_power", feed_in.feedin_max_power)
        if mode is None or power is None:
            raise HomeAssistantError("feed-in limitation has not been read from the device yet")
        try:
            await feed_in.async_write_limit(mode, int(power))
        except (ModbusError, ValueError) as err:
            raise HomeAssistantError(f"could not write feed-in limit: {err}") from err
        self.coordinator.pending.pop("feedin_limitation_mode", None)
        self.coordinator.pending.pop("feedin_max_power", None)
        await self.coordinator.async_request_refresh()


class ActivePowerControlUpdateButton(SofarEntity, ButtonEntity):
    """Active Power Control: Update — writes the staged (or last-read) enable flag and limit together."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Active Power Control: Update"

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "active_power_control_update", "active_power_control")

    async def async_press(self) -> None:
        active_power_control = self.coordinator.device.active_power_control
        enabled = resolve_active_power_control_enabled(self.coordinator)
        limit = self.coordinator.pending_or_live("active_power_export_limit", active_power_control.active_power_export_limit)
        if enabled is None or limit is None:
            raise HomeAssistantError("active power control has not been read from the device yet")
        try:
            await active_power_control.async_write_active_power_limit(enabled, limit)
        except (ModbusError, ValueError) as err:
            raise HomeAssistantError(f"could not write active power limit: {err}") from err
        self.coordinator.pending.pop("active_power_control_enabled", None)
        self.coordinator.pending.pop("active_power_export_limit", None)
        await self.coordinator.async_request_refresh()
