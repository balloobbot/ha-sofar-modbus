"""Switch platform: whether the active power control limit is armed.

Register 1105's Bit0 has to go out together with the limit percentage in
1106 (see sofar_modbus.modern.ActivePowerControl), so this stages a plain
bool in coordinator.pending instead of writing on toggle — the paired
"Active Power Control: Update" button (button.py) commits both together.
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from sofar_modbus.modern import PowerControlFlags

from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator
from .entity import SofarEntity

_KEY = "active_power_control_enabled"


def resolve_active_power_control_enabled(coordinator: SofarDataUpdateCoordinator) -> bool | None:
    """The enabled state this switch is currently showing — pending or live.

    Shared with button.py so "Active Power Control: Update" commits exactly
    what the switch displays, not a separately re-derived value.
    """
    flags = coordinator.device.active_power_control.power_control
    live = None if flags is None else PowerControlFlags.ACTIVE_POWER in flags
    return coordinator.pending_or_live(_KEY, live)


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    served = coordinator.data.updated | set(coordinator.data.failed)
    if "active_power_control" in served:
        async_add_entities([ActivePowerControlSwitch(coordinator)])


class ActivePowerControlSwitch(SofarEntity, SwitchEntity):
    """Active Power Control — staged; press Update to apply."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Active Power Control"

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        super().__init__(coordinator, _KEY, "active_power_control")

    @property
    def is_on(self) -> bool | None:
        return resolve_active_power_control_enabled(self.coordinator)

    async def async_turn_on(self, **kwargs: object) -> None:
        self.coordinator.pending[_KEY] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: object) -> None:
        self.coordinator.pending[_KEY] = False
        self.async_write_ha_state()
