"""Shared entity base — device_info and the coordinator plumbing."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import SofarDataUpdateCoordinator


class SofarEntity(CoordinatorEntity[SofarDataUpdateCoordinator]):
    """Base for every Sofar entity — one physical inverter per config entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SofarDataUpdateCoordinator, unique_id_suffix: str) -> None:
        super().__init__(coordinator)
        identity = coordinator.device.identity
        self._attr_unique_id = f"{identity.serial}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identity.serial)},
            name=coordinator.config_entry.title,
            manufacturer=ATTR_MANUFACTURER,
            model=identity.model or None,
            serial_number=identity.serial,
        )
