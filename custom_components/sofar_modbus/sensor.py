"""Sensor platform — one SensorEntity per row in generated_sensors.SENSOR_DESCRIPTIONS.

Only rows this inverter type actually serves get an entity. sofar_modbus has no
public "what will this device poll" surface (it settles that privately in
async_setup()) — only what one poll actually attempted, via UpdateReport. Since
every attempted component lands in exactly one of `updated` or `failed`, their
union is the served set, and the coordinator's first refresh (already run by
the time this platform is set up — see __init__.py) gives us one for free.

Each entity is also available independently of the others: sofar_modbus reads
components one at a time and contains a failed one in the poll's UpdateReport
rather than failing the whole update, so only the entities on a component that
actually failed this poll go unavailable — not all of them.
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
    report = coordinator.data
    served = report.updated | set(report.failed)

    entities = [
        SofarSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if description.component in served  # not served by this inverter type otherwise
    ]
    async_add_entities(entities)


class SofarSensor(SofarEntity, SensorEntity):
    """A read-only value off one of the device's Components."""

    entity_description: SofarSensorDescription

    def __init__(self, coordinator: SofarDataUpdateCoordinator, description: SofarSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if not super().available:
            return False  # the link is down; nothing refreshed at all
        report = self.coordinator.data
        return report is None or self.entity_description.component not in report.failed

    @property
    def native_value(self) -> object:
        component = getattr(self.coordinator.device, self.entity_description.component)
        return getattr(component, self.entity_description.key)
