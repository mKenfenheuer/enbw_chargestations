"""Sensor platform for the EnBW charge stations integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

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

    value_fn: Callable[[dict[str, Any]], int | str | datetime | None]


def _station_id(data: dict[str, Any]) -> str | None:
    """Return the station id as a string, if the payload carries one."""
    station_id = data.get("stationId")
    return None if station_id is None else str(station_id)


def _opening_hours(data: dict[str, Any]) -> str | None:
    """Return a human readable description of the opening hours."""
    opening_times = data.get("openingTimes") or {}
    if opening_times.get("twentyFourSeven"):
        return "24/7"
    return _compress_opening_hours(data.get("openingHours"))


_DAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
_DAY_PATTERN = re.compile(r"(?<![A-Za-z])(Mo|Di|Mi|Do|Fr|Sa|So):\s*")


def _compress_opening_hours(value: str | None) -> str | None:
    """Merge consecutive days with identical hours, e.g. "Mo-Fr: 08:00 - 20:00"."""
    if not value:
        return value
    parts = _DAY_PATTERN.split(value)
    # parts: [prefix, day, hours, day, hours, ...]
    if parts[0].strip() or len(parts) < 3:
        return value
    entries = [(parts[i], parts[i + 1].strip()) for i in range(1, len(parts), 2)]
    if any(not hours for _, hours in entries):
        return value

    groups: list[list[Any]] = []  # [first_day, last_day, hours]
    for day, hours in entries:
        if (
            groups
            and groups[-1][2] == hours
            and _DAYS.index(day) == _DAYS.index(groups[-1][1]) + 1
        ):
            groups[-1][1] = day
        else:
            groups.append([day, day, hours])

    def label(first: str, last: str) -> str:
        if first == last:
            return first
        return f"{first}-{last}"

    return ", ".join(f"{label(f, l)}: {h}" for f, l, h in groups)


def _next_opening_time(data: dict[str, Any]) -> datetime | None:
    """Return when the station next opens, if it is currently closed."""
    opening_times = data.get("openingTimes") or {}
    value = opening_times.get("nextOpeningTime")
    return dt_util.parse_datetime(value) if value else None


def _next_closing_time(data: dict[str, Any]) -> datetime | None:
    """Return when the station next closes, if it is currently open."""
    opening_times = data.get("openingTimes") or {}
    value = opening_times.get("nextClosingTime")
    return dt_util.parse_datetime(value) if value else None


SENSORS: tuple[EnbwSensorEntityDescription, ...] = (
    EnbwSensorEntityDescription(
        key="station_number",
        translation_key="station_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_station_id,
    ),
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
    EnbwSensorEntityDescription(
        key="opening_hours",
        translation_key="opening_hours",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_opening_hours,
    ),
    EnbwSensorEntityDescription(
        key="next_opening_time",
        translation_key="next_opening_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_opening_time,
    ),
    EnbwSensorEntityDescription(
        key="next_closing_time",
        translation_key="next_closing_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_closing_time,
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
    def native_value(self) -> int | str | datetime | None:
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
