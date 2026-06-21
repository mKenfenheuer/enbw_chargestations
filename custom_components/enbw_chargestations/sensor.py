"""Sensor platform for the EnBW charge stations integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UPDATED_AT,
)
from .coordinator import EnbwConfigEntry, EnbwDataUpdateCoordinator
from .entity import EnbwEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EnbwSensorEntityDescription(SensorEntityDescription):
    """Describes an EnBW sensor entity."""

    value_fn: Callable[[dict[str, Any]], int | None]


SENSORS: tuple[EnbwSensorEntityDescription, ...] = (
    EnbwSensorEntityDescription(
        key="total_charge_points",
        translation_key="total_charge_points",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("numberOfChargePoints"),
    ),
    EnbwSensorEntityDescription(
        key="available_charge_points",
        translation_key="available_charge_points",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("availableChargePoints"),
    ),
    EnbwSensorEntityDescription(
        key="unknown_state_charge_points",
        translation_key="unknown_state_charge_points",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("unknownStateChargePoints"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnbwConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EnBW sensors from a config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        EnbwSensor(coordinator, description) for description in SENSORS
    )


class EnbwSensor(EnbwEntity, SensorEntity):
    """Representation of an EnBW charge station sensor."""

    entity_description: EnbwSensorEntityDescription

    def __init__(
        self,
        coordinator: EnbwDataUpdateCoordinator,
        description: EnbwSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"enbw_station_{coordinator.station_number}_{description.key}"
        )

    @property
    def native_value(self) -> int | None:
        """Return the value of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return location info on the available charge points sensor."""
        if self.entity_description.key != "available_charge_points":
            return None
        data = self.coordinator.data
        if data is None:
            return None
        return {
            ATTR_LATITUDE: str(data.get("lat")),
            ATTR_LONGITUDE: str(data.get("lon")),
            ATTR_UPDATED_AT: datetime.now(tz=timezone.utc),
        }
