"""DataUpdateCoordinator for the EnBW charge stations integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import EnbwApiClient, EnbwApiError, EnbwAuthError
from .const import API_KEY, DOMAIN, STATION_NUMBER

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)

type EnbwConfigEntry = ConfigEntry[EnbwDataUpdateCoordinator]


class EnbwDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that keeps a single charge station up to date."""

    config_entry: EnbwConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: EnbwConfigEntry) -> None:
        """Initialize the coordinator."""
        self.station_number: str = config_entry.data[STATION_NUMBER]
        self.client = EnbwApiClient(
            async_get_clientsession(hass), config_entry.data[API_KEY]
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} {self.station_number}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data for the configured station."""
        try:
            return await self.client.async_get_charge_station(self.station_number)
        except EnbwAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except EnbwApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
