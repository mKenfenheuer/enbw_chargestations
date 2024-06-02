"""Config flow for Pi Assistant component."""

from __future__ import annotations

import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.util.location import distance
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

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


class ChargeStationModel:
    """ChargeStationObject."""

    def __init__(self, json, hass: HomeAssistant) -> None:
        """Initialize."""
        if not isinstance(json, dict):
            raise KeyError("Json not dict")
        self.station_number = json["stationId"]
        self.address = json["shortAddress"]
        self.plug_types = json["plugTypeNames"]
        self.max_power_in_kw = json["maxPowerInKw"]
        self.charge_points = json["numberOfChargePoints"]
        self.station_location = {"latitude": json["lat"], "longitude": json["lon"]}
        self.home_location = {
            "latitude": hass.config.latitude,
            "longitude": hass.config.longitude,
        }
        self.distance_to_home = distance(
            self.home_location["latitude"],
            self.home_location["longitude"],
            self.station_location["latitude"],
            self.station_location["longitude"],
        )


class EnbwChargeStationsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow ."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self.stations: list[ChargeStationModel] = []
        self.api_key: str | None = None
        self.latitude: float = 0
        self.longitude: float = 0
        self.search_radius: float = 10
        self.station_number: str = ""
        self.name: str = ""

    def get_charge_station(
        self, station_number: str, api_key: str, hass: HomeAssistant
    ) -> ChargeStationModel:
        """Get charge station from api."""
        try:
            http_response = requests.get(
                f"https://enbw-emp.azure-api.net/emobility-public-api/api/v1/chargestations/{station_number}",
                headers={
                    "User-Agent": "Home Assistant",
                    "Ocp-Apim-Subscription-Key": api_key,
                    "Origin": "https://www.enbw.com",
                    "Referer": "https://www.enbw.com/",
                },
                timeout=1,
            )
            if http_response.status_code >= 400:
                return None
            response = http_response.json()
            return ChargeStationModel(response, hass)
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.exception(ex)
            return None

    async def async_get_charge_station(
        self, station_number: str, api_key: str, hass: HomeAssistant
    ) -> ChargeStationModel:
        """Get charge station from api."""
        return await hass.async_add_executor_job(
            self.get_charge_station, station_number, api_key, hass
        )

    def get_charge_stations(
        self,
        fromLat: float,
        fromLong: float,
        toLat: float,
        toLong: float,
        api_key: str,
        hass: HomeAssistant,
        grouping: bool = False,
    ) -> list[ChargeStationModel]:
        """Get Chargestations."""
        url = f"https://enbw-emp.azure-api.net/emobility-public-api/api/v1/chargestations?fromLat={fromLat}&toLat={toLat}&fromLon={fromLong}&toLon={toLong}&grouping=false&groupingDivisor=15"
        try:
            http_response = requests.get(
                url,
                headers={
                    "User-Agent": "Home Assistant",
                    "Ocp-Apim-Subscription-Key": api_key,
                    "Origin": "https://www.enbw.com",
                    "Referer": "https://www.enbw.com/",
                },
                timeout=1,
            )
            if http_response.status_code >= 400:
                return []
            response = http_response.json()
            stations = [x for x in response if isinstance(x, dict)]
            stations = [ChargeStationModel(x, hass) for x in stations]
            stations = [x for x in stations if x.station_number is not None]
            stations.sort(key=lambda x: x.distance_to_home)
            return stations[:15]
        except Exception as ex:
            _LOGGER.exception(ex)
            return []

    async def async_get_charge_stations(
        self,
        fromLat: float,
        fromLong: float,
        toLat: float,
        toLong: float,
        api_key: str,
        hass: HomeAssistant,
        grouping: bool = False,
    ) -> list[ChargeStationModel]:
        """Get Chargestations."""
        return await hass.async_add_executor_job(
            self.get_charge_stations,
            fromLat,
            fromLong,
            toLat,
            toLong,
            api_key,
            hass,
            grouping,
        )

    def generate_schema(self):
        """Geneate Schema."""

        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude

        return {
            vol.Required(NAME, default="Charge Station"): str,
            vol.Optional(STATION_NUMBER, default=""): str,
            vol.Required(LATITUDE, default=latitude): cv.latitude,
            vol.Required(LONGITUDE, default=longitude): cv.longitude,
            vol.Required(SEARCH_RADIUS, default=10): cv.positive_float,
            vol.Required(
                API_KEY,
            ): str,
        }

    def generate_schema_config(self, config_entry: ConfigEntry):
        """Geneate Schema."""

        return {
            vol.Required(
                NAME, default=config_entry.data.get(NAME, "Charge Station")
            ): str,
            vol.Required(
                STATION_NUMBER, default=config_entry.data.get(STATION_NUMBER, "393894")
            ): str,
            vol.Required(
                API_KEY,
                default=config_entry.data.get(API_KEY, ""),
            ): str,
        }

    def generate_schema_select(self):
        """Geneate Schema."""

        return {
            vol.Required(STATION_NUMBER): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(
                            value=str(x.station_number),
                            label=f"{x.address} ({round(x.distance_to_home / 1000, 1)} km, {x.max_power_in_kw} kw)",
                        )
                        for x in self.stations
                    ],
                    multiple=False,
                    mode=SelectSelectorMode.LIST,
                )
            ),
        }

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Reconfigure step."""
        config = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        data_schema = self.generate_schema_config(config)

        errors = {}

        if user_input is not None:
            try:
                self.hass.config_entries.async_update_entry(
                    entry=config, data=user_input
                )
                await self.hass.config_entries.async_reload(config.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unknown exception.")
                errors["base"] = "Unknown exception."

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(data_schema),
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""

        errors = {}

        data_schema = self.generate_schema()

        if user_input is not None:
            try:
                # self._async_abort_entries_match(
                #    {STATION_NUMBER: user_input[STATION_NUMBER]}
                # )

                self.api_key = user_input[API_KEY]
                self.station_number = user_input[STATION_NUMBER]
                self.name = user_input[NAME]
                self.latitude = user_input[LATITUDE]
                self.longitude = user_input[LONGITUDE]
                self.search_radius = user_input[SEARCH_RADIUS]
                station = await self.async_get_charge_station(
                    self.station_number, self.api_key, self.hass
                )
                if station is not None:
                    # Station found
                    self.stations.append(station)

                if len(self.stations) == 0:
                    self.stations = await self.async_get_charge_stations(
                        self.latitude - DEG_PER_KM * 0.5 * self.search_radius,
                        self.longitude - DEG_PER_KM * 0.5 * self.search_radius,
                        self.latitude + DEG_PER_KM * 0.5 * self.search_radius,
                        self.longitude + DEG_PER_KM * 0.5 * self.search_radius,
                        self.api_key,
                        self.hass,
                        False,
                    )
                    return self.async_show_form(
                        step_id="search_station",
                        data_schema=vol.Schema(self.generate_schema_select()),
                    )

                self._async_abort_entries_match({STATION_NUMBER: self.station_number})
                return self.async_create_entry(
                    title=user_input.get(
                        NAME,
                    ),
                    data=user_input,
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unknown exception.")
                errors["base"] = "Unknown exception."

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))

    async def async_step_search_station(self, user_input: dict[str, Any] | None = None):
        """Handle the search_station step."""

        errors = {}

        if user_input is not None:
            try:
                self.station_number = user_input[STATION_NUMBER]
                self._async_abort_entries_match({STATION_NUMBER: self.station_number})
                return self.async_create_entry(
                    title=self.name,
                    data={
                        STATION_NUMBER: self.station_number,
                        API_KEY: self.api_key,
                        NAME: self.name,
                    },
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unknown exception.")
                errors["base"] = "Unknown exception."

        if len(self.stations) == 0:
            self.stations = await self.async_get_charge_stations(
                self.latitude - DEG_PER_KM * 0.5 * self.search_radius,
                self.longitude - DEG_PER_KM * 0.5 * self.search_radius,
                self.latitude + DEG_PER_KM * 0.5 * self.search_radius,
                self.longitude + DEG_PER_KM * 0.5 * self.search_radius,
                self.api_key,
                self.hass,
                False,
            )
            return self.async_show_form(
                step_id="search_station",
                data_schema=vol.Schema(self.generate_schema_select()),
            )

        return self.async_abort(reason="unknown_error")
