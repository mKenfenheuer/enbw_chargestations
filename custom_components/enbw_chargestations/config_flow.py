"""Config flow for the EnBW Charge Stations integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util.location import distance

from .api import EnbwApiClient, EnbwApiError, EnbwAuthError
from .const import (
    API_KEY,
    DEFAULT_SEARCH_RADIUS_M,
    DEG_PER_KM,
    DOMAIN,
    LOCATION,
    MAX_SEARCH_RESULTS,
    NAME,
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


def _station_name(station: dict[str, Any], station_number: str) -> str:
    """Derive the entry name from the station itself."""
    address = station.get("shortAddress")
    return str(address) if address else f"Charge station {station_number}"


class EnbwChargeStationsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EnBW Charge Stations."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._api_key: str = ""
        self._latitude: float = 0
        self._longitude: float = 0
        self._search_radius: float = 10
        self._station_options: list[SelectOptionDict] = []
        self._station_names: dict[str, str] = {}

    def _client(self) -> EnbwApiClient:
        return EnbwApiClient(async_get_clientsession(self.hass), self._api_key)

    def _existing_api_key(self) -> str | None:
        """Return the API key of an already configured charge station, if any."""
        for entry in self._async_current_entries():
            if api_key := entry.data.get(API_KEY):
                return api_key
        return None

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
        nearest = scored[:MAX_SEARCH_RESULTS]
        self._station_names = {
            str(station["stationId"]): _station_name(
                station, str(station["stationId"])
            )
            for station, _ in nearest
        }
        return [_station_option(station, dist) for station, dist in nearest]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        existing_api_key = self._existing_api_key()

        if user_input is not None:
            self._api_key = user_input.get(API_KEY) or existing_api_key or ""
            location = user_input[LOCATION]
            self._latitude = location["latitude"]
            self._longitude = location["longitude"]
            # The map hands the radius back in meters, the search works in km.
            self._search_radius = (
                location.get("radius", DEFAULT_SEARCH_RADIUS_M) / 1000
            )
            try:
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

        # The API key comes first, the search area map below it.
        schema: dict[Any, Any] = {}
        if existing_api_key:
            schema[vol.Optional(API_KEY)] = str
        else:
            schema[vol.Required(API_KEY)] = str
        schema[
            vol.Required(
                LOCATION,
                default={
                    "latitude": self.hass.config.latitude,
                    "longitude": self.hass.config.longitude,
                    "radius": DEFAULT_SEARCH_RADIUS_M,
                },
            )
        ] = LocationSelector(LocationSelectorConfig(radius=True))

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_search_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle selecting a station from the search results."""
        if user_input is not None:
            station_number = user_input[STATION_NUMBER]
            return await self._async_create(
                station_number,
                self._station_names.get(
                    station_number, f"Charge station {station_number}"
                ),
            )

        return self.async_show_form(
            step_id="search_station",
            data_schema=vol.Schema(
                {
                    vol.Required(STATION_NUMBER): SelectSelector(
                        SelectSelectorConfig(
                            options=self._station_options,
                            multiple=False,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def _async_create(
        self, station_number: str, name: str
    ) -> ConfigFlowResult:
        """Create the config entry for the selected station."""
        await self.async_set_unique_id(station_number)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=name,
            data={
                STATION_NUMBER: station_number,
                API_KEY: self._api_key,
                NAME: name,
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
