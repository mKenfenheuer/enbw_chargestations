"""Device tracker platform exposing the charge station location (issue #12)."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import EnbwConfigEntry, EnbwDataUpdateCoordinator
from .entity import EnbwEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnbwConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EnBW device tracker from a config entry."""
    async_add_entities([EnbwLocationTracker(config_entry.runtime_data)])


class EnbwLocationTracker(EnbwEntity, TrackerEntity):
    """Expose the geographic location of the charge station on the map."""

    _attr_translation_key = "location"

    def __init__(self, coordinator: EnbwDataUpdateCoordinator) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self._attr_unique_id = f"enbw_station_{coordinator.station_number}_location"

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the charge station."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("lat")

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the charge station."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("lon")
