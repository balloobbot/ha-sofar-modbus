"""Select platform: two write-capable modes.

``remote`` writes immediately — its one register is a plain field write, no
device-side pairing. ``feed_in`` stages its choice in ``coordinator.pending``
instead: the device only accepts ``feedin_limitation_mode`` and
``feedin_max_power`` as one combined write, so a separate button entity
(``button.py``) commits both together. See coordinator.py's ``pending_or_live``.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from modbus_connection import ModbusError

from sofar_modbus.modern import FeedinLimitationMode, RemoteSwitchOnOff

from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator
from .entity import SofarEntity

_REMOTE_SWITCH_OPTIONS = {
    RemoteSwitchOnOff.OFF: "Off",
    RemoteSwitchOnOff.ON: "On",
}

_FEEDIN_LIMITATION_OPTIONS = {
    FeedinLimitationMode.DISABLED: "Disabled",
    FeedinLimitationMode.ENABLED_FEED_IN_LIMITATION: "Enabled - Feed-in limitation",
    FeedinLimitationMode.ENABLED_3_PHASE_LIMIT: "Enabled - 3-phase limit",
}


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    served = coordinator.data.updated | set(coordinator.data.failed)
    entities: list[SelectEntity] = []
    if "remote" in served:
        entities.append(RemoteSwitchSelect(coordinator))
    if "feed_in" in served:
        entities.append(FeedInLimitationModeSelect(coordinator))
    async_add_entities(entities)


class RemoteSwitchSelect(SofarEntity, SelectEntity):
    """Remote Switch On Off — a plain single-register write, applied immediately."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(_REMOTE_SWITCH_OPTIONS.values())
    _attr_name = "Remote Switch On Off"

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "remote_switch_on_off", "remote")

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.device.remote.remote_switch_on_off
        return None if value is None else _REMOTE_SWITCH_OPTIONS[value]

    async def async_select_option(self, option: str) -> None:
        mode = next(k for k, v in _REMOTE_SWITCH_OPTIONS.items() if v == option)
        try:
            await self.coordinator.device.remote.write("remote_switch_on_off", mode)
        except ModbusError as err:
            raise HomeAssistantError(f"could not set remote switch: {err}") from err
        await self.coordinator.async_request_refresh()


class FeedInLimitationModeSelect(SofarEntity, SelectEntity):
    """FeedIn: Limitation Mode — staged; press FeedIn: Update to apply."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(_FEEDIN_LIMITATION_OPTIONS.values())
    _attr_name = "FeedIn: Limitation Mode"

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "feedin_limitation_mode", "feed_in")

    @property
    def current_option(self) -> str | None:
        live = self.coordinator.device.feed_in.feedin_limitation_mode
        value = self.coordinator.pending_or_live("feedin_limitation_mode", live)
        return None if value is None else _FEEDIN_LIMITATION_OPTIONS[value]

    async def async_select_option(self, option: str) -> None:
        mode = next(k for k, v in _FEEDIN_LIMITATION_OPTIONS.items() if v == option)
        self.coordinator.pending["feedin_limitation_mode"] = mode
        self.async_write_ha_state()
