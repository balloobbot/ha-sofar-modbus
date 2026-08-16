"""Select platform: write-capable modes.

``remote``, ``charger`` and ``eps`` write immediately — each is a plain field
(or, for ``eps``, a field plus an always-zero reserved register the library
fills in) with no device-side pairing. ``feed_in`` and ``passive`` (timeout
action) stage their choice in ``coordinator.pending`` instead: the device only
accepts those registers as one combined write with a sibling number entity,
so a separate button entity (``button.py``) commits them together. See
coordinator.py's ``pending_or_live``.

Charger Use Mode and EPS Mode are HYBRID-only and have no HYBRID hardware to
verify against yet — see README's Status section.

The ``_XXX_OPTIONS`` dicts below map each device enum member to the
machine-readable option slug HA's state machine and ``select_option`` service
calls actually see; the human-readable text lives in strings.json's
``entity.select.<translation_key>.state`` block instead, so the frontend can
translate it. See homeassistant/components/select's option handling and
sensor.py's device_class=ENUM sensors for the same pattern.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from modbus_connection import ModbusError

# The PyPI library, not a self-import — see __init__.py
from sofar_modbus.modern import ChargerUseMode, EpsControlMode, FeedinLimitationMode, PassiveModeTimeoutAction, RemoteSwitchOnOff

from .coordinator import SofarConfigEntry, SofarSettingsCoordinator
from .entity import SofarEntity

_REMOTE_SWITCH_OPTIONS = {
    RemoteSwitchOnOff.OFF: "off",
    RemoteSwitchOnOff.ON: "on",
}

_FEEDIN_LIMITATION_OPTIONS = {
    FeedinLimitationMode.DISABLED: "disabled",
    FeedinLimitationMode.ENABLED_FEED_IN_LIMITATION: "enabled_feed_in_limitation",
    FeedinLimitationMode.ENABLED_3_PHASE_LIMIT: "enabled_3_phase_limit",
}

_CHARGER_USE_MODE_OPTIONS = {
    ChargerUseMode.SELF_USE: "self_use",
    ChargerUseMode.TIME_OF_USE: "time_of_use",
    ChargerUseMode.TIMING_MODE: "timing_mode",
    ChargerUseMode.PASSIVE_MODE: "passive_mode",
    ChargerUseMode.PEAK_CUT_MODE: "peak_cut_mode",
    ChargerUseMode.OFF_GRID_MODE: "off_grid_mode",
    ChargerUseMode.GENERATOR_MODE: "generator_mode",
    ChargerUseMode.FEED_IN_PRIORITY_MODE: "feed_in_priority_mode",
}

_EPS_MODE_OPTIONS = {
    EpsControlMode.TURN_OFF: "turn_off",
    EpsControlMode.TURN_ON_PROHIBIT_COLD_START: "turn_on_prohibit_cold_start",
    EpsControlMode.TURN_ON_ENABLE_COLD_START: "turn_on_enable_cold_start",
}

_PASSIVE_TIMEOUT_ACTION_OPTIONS = {
    PassiveModeTimeoutAction.FORCE_STANDBY: "force_standby",
    PassiveModeTimeoutAction.RETURN_TO_PREVIOUS_MODE: "return_to_previous_mode",
}


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data.settings
    served = coordinator.served_components
    entities: list[SelectEntity] = []
    if "remote" in served:
        entities.append(RemoteSwitchSelect(coordinator))
    if "feed_in" in served:
        entities.append(FeedInLimitationModeSelect(coordinator))
    if "charger" in served:
        entities.append(ChargerUseModeSelect(coordinator))
    if "eps" in served:
        entities.append(EpsModeSelect(coordinator))
    if "passive" in served:
        entities.append(PassiveTimeoutActionSelect(coordinator))
    async_add_entities(entities)


class RemoteSwitchSelect(SofarEntity[SofarSettingsCoordinator], SelectEntity):
    """Remote Switch On Off — a plain single-register write, applied immediately."""

    _attr_options = list(_REMOTE_SWITCH_OPTIONS.values())
    _attr_translation_key = "remote_switch_on_off"

    def __init__(self, coordinator: SofarSettingsCoordinator) -> None:
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


class FeedInLimitationModeSelect(SofarEntity[SofarSettingsCoordinator], SelectEntity):
    """FeedIn: Limitation Mode — staged; press FeedIn: Update to apply."""

    _attr_options = list(_FEEDIN_LIMITATION_OPTIONS.values())
    _attr_translation_key = "feedin_limitation_mode"

    def __init__(self, coordinator: SofarSettingsCoordinator) -> None:
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


class ChargerUseModeSelect(SofarEntity[SofarSettingsCoordinator], SelectEntity):
    """Charger Use Mode — a plain single-register write, applied immediately."""

    _attr_options = list(_CHARGER_USE_MODE_OPTIONS.values())
    _attr_translation_key = "charger_use_mode"

    def __init__(self, coordinator: SofarSettingsCoordinator) -> None:
        super().__init__(coordinator, "charger_use_mode", "charger")

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.device.charger.charger_use_mode
        return None if value is None else _CHARGER_USE_MODE_OPTIONS[value]

    async def async_select_option(self, option: str) -> None:
        mode = next(k for k, v in _CHARGER_USE_MODE_OPTIONS.items() if v == option)
        try:
            await self.coordinator.device.charger.write("charger_use_mode", mode)
        except ModbusError as err:
            raise HomeAssistantError(f"could not set charger use mode: {err}") from err
        await self.coordinator.async_request_refresh()


class EpsModeSelect(SofarEntity[SofarSettingsCoordinator], SelectEntity):
    """EPS Mode — applied immediately.

    The wait-time register is a reserved function the library always writes
    as 0 alongside it (see ``EpsControl.async_write_control``), so there is
    nothing to stage.
    """

    _attr_options = list(_EPS_MODE_OPTIONS.values())
    _attr_translation_key = "eps_control"

    def __init__(self, coordinator: SofarSettingsCoordinator) -> None:
        super().__init__(coordinator, "eps_control", "eps")

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.device.eps.eps_control
        return None if value is None else _EPS_MODE_OPTIONS[value]

    async def async_select_option(self, option: str) -> None:
        mode = next(k for k, v in _EPS_MODE_OPTIONS.items() if v == option)
        try:
            await self.coordinator.device.eps.async_write_control(mode)
        except ModbusError as err:
            raise HomeAssistantError(f"could not set EPS mode: {err}") from err
        await self.coordinator.async_request_refresh()


class PassiveTimeoutActionSelect(SofarEntity[SofarSettingsCoordinator], SelectEntity):
    """Passive: Timeout Action — staged; press Passive: Timeout Update to apply."""

    _attr_options = list(_PASSIVE_TIMEOUT_ACTION_OPTIONS.values())
    _attr_translation_key = "passive_mode_timeout_action"

    def __init__(self, coordinator: SofarSettingsCoordinator) -> None:
        super().__init__(coordinator, "passive_mode_timeout_action", "passive")

    @property
    def current_option(self) -> str | None:
        live = self.coordinator.device.passive.passive_mode_timeout_action
        value = self.coordinator.pending_or_live("passive_mode_timeout_action", live)
        return None if value is None else _PASSIVE_TIMEOUT_ACTION_OPTIONS[value]

    async def async_select_option(self, option: str) -> None:
        action = next(k for k, v in _PASSIVE_TIMEOUT_ACTION_OPTIONS.items() if v == option)
        self.coordinator.pending["passive_mode_timeout_action"] = action
        self.async_write_ha_state()
