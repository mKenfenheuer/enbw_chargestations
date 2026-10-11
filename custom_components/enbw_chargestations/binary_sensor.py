"""Binary sensor platform for the EnBW charge stations integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ADDRESS,
    ATTR_ALWAYS_OPEN,
    ATTR_AVAILABLE_CHARGE_POINTS,
    ATTR_CABLE_ATTACHED,
    ATTR_CLOSED_ON_HOLIDAYS,
    ATTR_EVSE_ID,
    ATTR_MAX_POWER_IN_KW,
    ATTR_MAX_POWER_PER_PLUG_TYPE_IN_KW,
    ATTR_NEXT_CLOSING_TIME,
    ATTR_NEXT_OPENING_TIME,
    ATTR_OPENING_HOURS,
    ATTR_OUT_OF_SERVICE,
    ATTR_PLUG_TYPE_NAME,
    ATTR_STATE,
    ATTR_STATION_ID,
    ATTR_TOTAL_CHARGE_POINTS,
    ATTR_UPDATED_AT,
)
from .coordinator import EnbwConfigEntry, EnbwDataUpdateCoordinator
from .entity import EnbwEntity

PARALLEL_UPDATES = 0


def _station_is_open(data: dict[str, Any]) -> bool | None:
    """Return whether the station is currently open, if known."""
    opening_times = data.get("openingTimes") or {}
    if opening_times.get("twentyFourSeven"):
        return True
    if "nextClosingTime" in opening_times:
        return True
    if "nextOpeningTime" in opening_times:
        return False
    return None


@dataclass(frozen=True, kw_only=True)
class EnbwBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an EnBW diagnostic binary sensor entity."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]


DIAGNOSTIC_BINARY_SENSORS: tuple[EnbwBinarySensorEntityDescription, ...] = (
    EnbwBinarySensorEntityDescription(
        key="always_open",
        translation_key="always_open",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (data.get("openingTimes") or {}).get(
            "twentyFourSeven"
        ),
    ),
    EnbwBinarySensorEntityDescription(
        key="closed_on_holidays",
        translation_key="closed_on_holidays",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (data.get("openingTimes") or {}).get(
            "closedOnHolidays"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnbwConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EnBW binary sensors from a config entry."""
    coordinator = config_entry.runtime_data

    entities: list[BinarySensorEntity] = [
        ChargeStationStateBinarySensor(coordinator),
        StationOpenBinarySensor(coordinator),
    ]
    entities.extend(
        EnbwDiagnosticBinarySensor(coordinator, description)
        for description in DIAGNOSTIC_BINARY_SENSORS
    )

    data = coordinator.data or {}
    for index, point in enumerate(data.get("chargePoints", []), start=1):
        max_power = max(
            (c.get("maxPowerInKw", 0) for c in point.get("connectors", [])),
            default=0,
        )
        entities.append(
            ChargePointBinarySensor(coordinator, point["evseId"], index, max_power)
        )

    async_add_entities(entities)


class ChargeStationStateBinarySensor(EnbwEntity, BinarySensorEntity):
    """Binary sensor reporting whether the station has free charge points."""

    _attr_translation_key = "charge_station"
    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    def __init__(self, coordinator: EnbwDataUpdateCoordinator) -> None:
        """Initialize the station state binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"enbw_station_{coordinator.station_number}_state"

    @property
    def is_on(self) -> bool | None:
        """Return True if at least one charge point is free and reachable."""
        data = self.coordinator.data
        if data is None:
            return None
        if data.get("availableChargePoints", 0) <= 0:
            return False
        return _station_is_open(data) is not False

    @property
    def icon(self) -> str:
        """Return the icon for the entity."""
        return "mdi:car-electric-outline" if self.is_on else "mdi:car-electric"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes describing the station."""
        data = self.coordinator.data
        if data is None:
            return None

        plug_type_names = data.get("plugTypeNames", [])
        connectors = [
            connector
            for point in data.get("chargePoints", [])
            for connector in point.get("connectors", [])
        ]

        plug_type_cable_attached = {
            name: any(c.get("cableAttached") for c in connectors)
            for name in plug_type_names
        }
        plug_type_power = {
            name: max(
                (c.get("maxPowerInKw", 0) for c in connectors), default=0
            )
            for name in plug_type_names
        }

        return {
            ATTR_CABLE_ATTACHED: plug_type_cable_attached,
            ATTR_PLUG_TYPE_NAME: plug_type_names,
            ATTR_MAX_POWER_IN_KW: data.get("maxPowerInKw"),
            ATTR_MAX_POWER_PER_PLUG_TYPE_IN_KW: plug_type_power,
            ATTR_STATION_ID: str(data.get("stationId")),
            ATTR_ADDRESS: data.get("shortAddress"),
            ATTR_AVAILABLE_CHARGE_POINTS: data.get("availableChargePoints"),
            ATTR_TOTAL_CHARGE_POINTS: data.get("numberOfChargePoints"),
            ATTR_UPDATED_AT: datetime.now(tz=timezone.utc),
        }


class ChargePointBinarySensor(EnbwEntity, BinarySensorEntity):
    """Binary sensor reporting the occupancy of a single charge point."""

    _attr_translation_key = "charge_point"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        coordinator: EnbwDataUpdateCoordinator,
        point_id: str,
        index: int,
        max_power_in_kw: float,
    ) -> None:
        """Initialize a charge point binary sensor."""
        super().__init__(coordinator)
        self._point_id = point_id
        self._attr_translation_placeholders = {
            "index": str(index),
            "power": f"{max_power_in_kw:g}",
        }
        self._attr_unique_id = (
            f"enbw_station_{coordinator.station_number}_charge_point_{index}"
        )

    def _point(self) -> dict[str, Any] | None:
        """Return the data for this charge point, if present."""
        data = self.coordinator.data
        if data is None:
            return None
        for point in data.get("chargePoints", []):
            if point.get("evseId") == self._point_id:
                return point
        return None

    @property
    def available(self) -> bool:
        """Return True if this charge point is present in the latest data."""
        return super().available and self._point() is not None

    @property
    def is_on(self) -> bool | None:
        """Return True if the charge point is occupied or unreachable."""
        point = self._point()
        if point is None:
            return None
        if point.get("status") != "AVAILABLE":
            return True
        data = self.coordinator.data
        return data is not None and _station_is_open(data) is False

    @property
    def icon(self) -> str:
        """Return the icon based on plug type, power and occupancy."""
        point = self._point()
        if point is None:
            return "mdi:car-electric"
        connectors = point.get("connectors", [])
        if self.is_on:
            return "mdi:car-electric-outline"
        if len(connectors) > 1:
            return "mdi:car-electric"
        connector = connectors[0] if connectors else None
        plug_type_name = connector.get("plugTypeName") if connector else None
        if plug_type_name == "CHAdeMO":
            return "mdi:ev-plug-chademo"
        if plug_type_name and "tesla" in plug_type_name.lower():
            return "mdi:ev-plug-tesla"
        max_power = connector.get("maxPowerInKw") if connector else None
        if max_power is not None and max_power > 22:
            return "mdi:ev-plug-ccs2"
        return "mdi:ev-plug-type2"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes for this charge point."""
        point = self._point()
        data = self.coordinator.data
        if point is None or data is None:
            return None

        connectors = point.get("connectors", [])
        return {
            ATTR_CABLE_ATTACHED: [c.get("cableAttached") for c in connectors],
            ATTR_PLUG_TYPE_NAME: [c.get("plugTypeName") for c in connectors],
            ATTR_MAX_POWER_IN_KW: [c.get("maxPowerInKw") for c in connectors],
            ATTR_ADDRESS: data.get("shortAddress"),
            ATTR_EVSE_ID: point.get("evseId"),
            ATTR_STATE: str(point.get("status")),
            ATTR_STATION_ID: str(data.get("stationId")),
            ATTR_UPDATED_AT: datetime.now(tz=timezone.utc),
            ATTR_OUT_OF_SERVICE: point.get("status") == "OUT_OF_SERVICE",
        }


class StationOpenBinarySensor(EnbwEntity, BinarySensorEntity):
    """Binary sensor reporting whether the station is currently open."""

    _attr_translation_key = "station_open"

    def __init__(self, coordinator: EnbwDataUpdateCoordinator) -> None:
        """Initialize the station open binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"enbw_station_{coordinator.station_number}_open"

    @property
    def is_on(self) -> bool | None:
        """Return True if the station is currently open."""
        data = self.coordinator.data
        if data is None:
            return None
        return _station_is_open(data)

    @property
    def icon(self) -> str:
        """Return the icon for the entity."""
        return "mdi:door-open" if self.is_on else "mdi:door-closed"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the opening hours details for this station."""
        data = self.coordinator.data
        if data is None:
            return None
        opening_times = data.get("openingTimes") or {}
        return {
            ATTR_ALWAYS_OPEN: data.get("alwaysOpen"),
            ATTR_OPENING_HOURS: data.get("openingHours"),
            ATTR_CLOSED_ON_HOLIDAYS: opening_times.get("closedOnHolidays"),
            ATTR_NEXT_OPENING_TIME: opening_times.get("nextOpeningTime"),
            ATTR_NEXT_CLOSING_TIME: opening_times.get("nextClosingTime"),
            ATTR_STATION_ID: str(data.get("stationId")),
            ATTR_UPDATED_AT: datetime.now(tz=timezone.utc),
        }


class EnbwDiagnosticBinarySensor(EnbwEntity, BinarySensorEntity):
    """Representation of a diagnostic EnBW binary sensor described declaratively."""

    entity_description: EnbwBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: EnbwDataUpdateCoordinator,
        description: EnbwBinarySensorEntityDescription,
    ) -> None:
        """Initialize the diagnostic binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"enbw_station_{coordinator.station_number}_{description.key}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return the value of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.is_on_fn(self.coordinator.data)
