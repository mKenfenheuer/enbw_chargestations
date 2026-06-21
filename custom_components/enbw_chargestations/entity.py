"""Base entity for the EnBW charge stations integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnbwDataUpdateCoordinator


class EnbwEntity(CoordinatorEntity[EnbwDataUpdateCoordinator]):
    """Base class for all EnBW charge station entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EnbwDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"enbw_station_{coordinator.station_number}")},
            name=coordinator.config_entry.title,
            manufacturer="EnBW Energie Baden-Württemberg",
            model="Charge Station",
            configuration_url="https://www.enbw.com/elektromobilitaet/produkte/mobilityplus-app/ladestation-finden/map",
        )

    @property
    def available(self) -> bool:
        """Return True if the coordinator has data."""
        return super().available and self.coordinator.data is not None
