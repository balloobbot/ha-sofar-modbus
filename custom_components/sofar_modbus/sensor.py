"""Sensor platform — one SensorEntity per row in generated_sensors.SENSOR_DESCRIPTIONS.

Only rows this inverter type actually serves get an entity, checked against
SofarInverter's *_served_keys sets (device.py) — not against
Component.declared_fields, which restrict_fields() deliberately leaves
describing the full static layout regardless of what was excluded.
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
        served_keys = getattr(device, f"{description.component}_served_keys")
        if description.key not in served_keys:
            continue  # not served by this inverter type
        entities.append(SofarSensor(coordinator, description))

    async_add_entities(entities)


class SofarSensor(SofarEntity, SensorEntity):
    """A read-only value off one of the device's Components."""

    entity_description: SofarSensorDescription

    def __init__(self, coordinator: SofarDataUpdateCoordinator, description: SofarSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> object:
        component = getattr(self.coordinator.device, self.entity_description.component)
        return getattr(component, self.entity_description.key)
