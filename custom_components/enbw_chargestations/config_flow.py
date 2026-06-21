"""Config flow for the EnBW Charge Stations integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util.location import distance

from .api import EnbwApiClient, EnbwApiError, EnbwAuthError
from .const import (
    API_KEY,
    DEG_PER_KM,
    DOMAIN,
    LATITUDE,
    LONGITUDE,
    NAME,
    SEARCH_RADIUS,
    STATION_NUMBER,
)

_LOGGER = logging.getLogger(__name__)


def _station_option(station: dict[str, Any], distance_m: float) -> SelectOptionDict:
    """Build a select option from a station payload."""
    return SelectOptionDict(
        value=str(station["stationId"]),
        label=(
            f"{station.get('shortAddress')} "
            f"({round(distance_m / 1000, 1)} km, "
            f"{station.get('maxPowerInKw')} kw)"
        ),
    )


class EnbwChargeStationsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EnBW Charge Stations."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._api_key: str = ""
        self._name: str = "Charge Station"
        self._latitude: float = 0
        self._longitude: float = 0
        self._search_radius: float = 10
        self._station_options: list[SelectOptionDict] = []

    def _client(self) -> EnbwApiClient:
        return EnbwApiClient(async_get_clientsession(self.hass), self._api_key)

    async def _async_search_stations(self) -> list[SelectOptionDict]:
        """Search stations around the configured location."""
        client = self._client()
        half = DEG_PER_KM * 0.5 * self._search_radius
        stations = await client.async_get_charge_stations(
            self._latitude - half,
            self._longitude - half,
            self._latitude + half,
            self._longitude + half,
        )

        home_lat = self.hass.config.latitude
        home_lon = self.hass.config.longitude
        scored = [
            (
                station,
                distance(home_lat, home_lon, station["lat"], station["lon"]),
            )
            for station in stations
            if station.get("stationId") is not None
        ]
        scored.sort(key=lambda item: item[1])
        return [_station_option(station, dist) for station, dist in scored[:15]]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._api_key = user_input[API_KEY]
            self._name = user_input[NAME]
            self._latitude = user_input[LATITUDE]
            self._longitude = user_input[LONGITUDE]
            self._search_radius = user_input[SEARCH_RADIUS]
            station_number = user_input.get(STATION_NUMBER, "").strip()

            try:
                if station_number:
                    # Validate the explicit station number.
                    await self._client().async_get_charge_station(station_number)
                    return await self._async_create(station_number)

                self._station_options = await self._async_search_stations()
            except EnbwAuthError:
                errors["base"] = "invalid_auth"
            except EnbwApiError:
                errors["base"] = "cannot_connect"
            else:
                if not self._station_options:
                    errors["base"] = "no_stations_found"
                else:
                    return await self.async_step_search_station()

        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(NAME, default="Charge Station"): str,
                    vol.Optional(STATION_NUMBER, default=""): str,
                    vol.Required(LATITUDE, default=latitude): cv.latitude,
                    vol.Required(LONGITUDE, default=longitude): cv.longitude,
                    vol.Required(SEARCH_RADIUS, default=10): cv.positive_float,
                    vol.Required(API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_search_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle selecting a station from the search results."""
        if user_input is not None:
            return await self._async_create(user_input[STATION_NUMBER])

        return self.async_show_form(
            step_id="search_station",
            data_schema=vol.Schema(
                {
                    vol.Required(STATION_NUMBER): SelectSelector(
                        SelectSelectorConfig(
                            options=self._station_options,
                            multiple=False,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def _async_create(self, station_number: str) -> ConfigFlowResult:
        """Create the config entry for the selected station."""
        await self.async_set_unique_id(station_number)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._name,
            data={
                STATION_NUMBER: station_number,
                API_KEY: self._api_key,
                NAME: self._name,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            self._api_key = user_input[API_KEY]
            station_number = user_input[STATION_NUMBER].strip()
            try:
                await self._client().async_get_charge_station(station_number)
            except EnbwAuthError:
                errors["base"] = "invalid_auth"
            except EnbwApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    title=user_input[NAME],
                    data={
                        NAME: user_input[NAME],
                        STATION_NUMBER: station_number,
                        API_KEY: self._api_key,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        NAME, default=entry.data.get(NAME, "Charge Station")
                    ): str,
                    vol.Required(
                        STATION_NUMBER, default=entry.data.get(STATION_NUMBER, "")
                    ): str,
                    vol.Required(
                        API_KEY, default=entry.data.get(API_KEY, "")
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when the API key is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with a new API key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            self._api_key = user_input[API_KEY]
            try:
                await self._client().async_get_charge_station(
                    entry.data[STATION_NUMBER]
                )
            except EnbwAuthError:
                errors["base"] = "invalid_auth"
            except EnbwApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, API_KEY: self._api_key},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(API_KEY): str}),
            errors=errors,
        )
