"""Sensor platform — one SensorEntity per row in generated_sensors.SENSOR_DESCRIPTIONS.

Only rows whose field survived this device's restrict_fields() (Phase 0 —
device.py, driven by sofar/const.py's per-field allowedtypes) get an entity:
a field the inverter doesn't serve reads as a missing attribute, so those
rows are filtered out here rather than showing a permanently-unavailable
entity.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SofarDataUpdateCoordinator
from .entity import SofarEntity
from .generated_sensors import SENSOR_DESCRIPTIONS, SofarSensorDescription


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SofarDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device

    entities: list[SofarSensor] = []
    for description in SENSOR_DESCRIPTIONS:
        component = getattr(device, description.component, None)
        if component is None:
            continue  # e.g. battery_pack on a PV-only inverter
        if description.key not in component.declared_fields:
            continue  # excluded by restrict_fields() for this inverter type
        entities.append(SofarSensor(coordinator, description))

    async_add_entities(entities)


class SofarSensor(SofarEntity, SensorEntity):
    """A read-only value off one of the device's Components."""

    entity_description: SofarSensorDescription

    def __init__(self, coordinator: SofarDataUpdateCoordinator, description: SofarSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_state_class = description.state_class
        self._attr_entity_category = description.entity_category
        self._attr_icon = description.icon
        self._attr_entity_registry_enabled_default = description.entity_registry_enabled_default
        self._attr_suggested_display_precision = description.suggested_display_precision

    @property
    def native_value(self) -> object:
        component = getattr(self.coordinator.device, self.entity_description.component)
        return getattr(component, self.entity_description.key)
