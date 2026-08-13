"""Shared entity base — device_info and the coordinator plumbing."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import SofarDataUpdateCoordinator


class SofarEntity(CoordinatorEntity[SofarDataUpdateCoordinator]):
    """Base for every Sofar entity — one physical inverter per config entry.

    ``component`` is the attribute name on ``coordinator.device`` this entity
    reads or writes (e.g. ``'grid'``, ``'feed_in'``) — used by ``available``
    below so only the entities on a component that actually failed this poll
    go unavailable, not all of them.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: SofarDataUpdateCoordinator, unique_id_suffix: str, component: str) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        serial = device.serial_number
        assert serial is not None  # set by async_setup(), which the coordinator's first refresh requires
        self._component = component
        self._attr_unique_id = f"{serial}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=coordinator.config_entry.title,
            manufacturer=ATTR_MANUFACTURER,
            model=device.model or None,
            serial_number=serial,
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False  # the link is down; nothing refreshed at all
        report = self.coordinator.data
        return report is None or self._component not in report.failed
