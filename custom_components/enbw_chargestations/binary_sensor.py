"""Binary sensor platform for the EnBW charge stations integration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ADDRESS,
    ATTR_AVAILABLE_CHARGE_POINTS,
    ATTR_CABLE_ATTACHED,
    ATTR_EVSE_ID,
    ATTR_MAX_POWER_IN_KW,
    ATTR_MAX_POWER_PER_PLUG_TYPE_IN_KW,
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnbwConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EnBW binary sensors from a config entry."""
    coordinator = config_entry.runtime_data

    entities: list[BinarySensorEntity] = [ChargeStationStateBinarySensor(coordinator)]

    data = coordinator.data or {}
    for index, point in enumerate(data.get("chargePoints", []), start=1):
        entities.append(
            ChargePointBinarySensor(coordinator, point["evseId"], index)
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
        """Return True if at least one charge point is available."""
        data = self.coordinator.data
        if data is None:
            return None
        return data.get("availableChargePoints", 0) > 0

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
    ) -> None:
        """Initialize a charge point binary sensor."""
        super().__init__(coordinator)
        self._point_id = point_id
        self._attr_translation_placeholders = {"index": str(index)}
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
        """Return True if the charge point is occupied (not available)."""
        point = self._point()
        if point is None:
            return None
        return point.get("status") != "AVAILABLE"

    @property
    def icon(self) -> str:
        """Return the icon based on plug type and occupancy."""
        point = self._point()
        if point is None:
            return "mdi:car-electric"
        plug_type_names = [
            connector.get("plugTypeName") for connector in point.get("connectors", [])
        ]
        if self.is_on:
            return "mdi:car-electric-outline"
        if len(plug_type_names) > 1:
            return "mdi:car-electric"
        first = plug_type_names[0] if plug_type_names else None
        if first in ("Typ 2", "Type 2"):
            return "mdi:ev-plug-type2"
        if first == "CCS (Typ 2)":
            return "mdi:ev-plug-ccs2"
        if first == "CHAdeMO":
            return "mdi:ev-plug-chademo"
        return "mdi:car-electric"

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
