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
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from modbus_connection import ModbusError

from sofar_modbus.modern import ChargerUseMode, EpsControlMode, FeedinLimitationMode, PassiveModeTimeoutAction, RemoteSwitchOnOff

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

_CHARGER_USE_MODE_OPTIONS = {
    ChargerUseMode.SELF_USE: "Self Use",
    ChargerUseMode.TIME_OF_USE: "Time Of Use",
    ChargerUseMode.TIMING_MODE: "Timing Mode",
    ChargerUseMode.PASSIVE_MODE: "Passive Mode",
    ChargerUseMode.PEAK_CUT_MODE: "Peak Cut Mode",
    ChargerUseMode.OFF_GRID_MODE: "Off Grid Mode",
}

_EPS_MODE_OPTIONS = {
    EpsControlMode.TURN_OFF: "Turn Off",
    EpsControlMode.TURN_ON_PROHIBIT_COLD_START: "Turn On - Prohibit Cold Start",
    EpsControlMode.TURN_ON_ENABLE_COLD_START: "Turn On - Enable Cold Start",
}

_PASSIVE_TIMEOUT_ACTION_OPTIONS = {
    PassiveModeTimeoutAction.FORCE_STANDBY: "Force Standby",
    PassiveModeTimeoutAction.RETURN_TO_PREVIOUS_MODE: "Return To Previous Mode",
}


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    served = coordinator.data.updated | set(coordinator.data.failed)
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


class RemoteSwitchSelect(SofarEntity, SelectEntity):
    """Remote Switch On Off — a plain single-register write, applied immediately."""

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


class ChargerUseModeSelect(SofarEntity, SelectEntity):
    """Charger Use Mode — a plain single-register write, applied immediately."""

    _attr_options = list(_CHARGER_USE_MODE_OPTIONS.values())
    _attr_name = "Charger Use Mode"

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
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


class EpsModeSelect(SofarEntity, SelectEntity):
    """EPS Mode — applied immediately.

    The wait-time register is a reserved function the library always writes
    as 0 alongside it (see ``EpsControl.async_write_control``), so there is
    nothing to stage.
    """

    _attr_options = list(_EPS_MODE_OPTIONS.values())
    _attr_name = "EPS Mode"

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
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


class PassiveTimeoutActionSelect(SofarEntity, SelectEntity):
    """Passive: Timeout Action — staged; press Passive: Timeout Update to apply."""

    _attr_options = list(_PASSIVE_TIMEOUT_ACTION_OPTIONS.values())
    _attr_name = "Passive: Timeout Action"

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
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
