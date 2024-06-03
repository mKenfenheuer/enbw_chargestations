"""Charge station implementation."""

from abc import abstractmethod
from datetime import datetime, timezone
import logging
from time import time
from typing import Any, override
import requests

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant

from .const import (
    ATTR_ADDRESS,
    ATTR_AVAILABLE_CHARGE_POINTS,
    ATTR_CABLE_ATTACHED,
    ATTR_EVSE_ID,
    ATTR_ICON_COLOR,
    ATTR_MAX_POWER_IN_KW,
    ATTR_MAX_POWER_PER_PLUG_TYPE_IN_KW,
    ATTR_PLUG_TYPE_NAME,
    ATTR_TOTAL_CHARGE_POINTS,
    ATTR_UPDATED_AT,
    DOMAIN,
)
from .utils import Utils

_LOGGER = logging.getLogger(__name__)

class ChargeStation:
    """Implementation for charge stations."""

    def __init__(
        self, hass: HomeAssistant, name: str, station_number: str, api_key: str
    ) -> None:
        """Initialize."""
        self.name: str = name
        self.hass: HomeAssistant = hass
        self.station_number: str = station_number
        self.api_key: str = api_key
        self.updated_at: float | None = None
        self.sensors: list[ChargeStationSensorEntity] = []
        self.binary_sensors: list[ChargeStationBinarySensorEntity] = []
        self.unique_id: str = f"enbw_station_{station_number}"
        self.updated_at: float = 0

    def update(self):
        """Update from rest api."""
        if self.updated_at > time() - 60:
            return
        self.updated_at = time()
        try:
            response = requests.get(
                f"https://enbw-emp.azure-api.net/emobility-public-api/api/v1/chargestations/{self.station_number}",
                headers={
                    "User-Agent": "Home Assistant",
                    "Ocp-Apim-Subscription-Key": self.api_key,
                    "Origin": "https://www.enbw.com",
                    "Referer": "https://www.enbw.com/",
                },
                timeout=1,
            ).json()
            if len(self.sensors) + len(self.binary_sensors) == 0:
                self.create_entities(response)
            for sensor in self.sensors:
                sensor.update_from_response(response)
            for binary_sensor in self.binary_sensors:
                binary_sensor.update_from_response(response)

        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.exception(ex)  # noqa: TRY401
            return False
        return True

    def create_entities(self, response):
        """Create and add entities to internal register."""
        self.binary_sensors.append(ChargeStationStateBinarySensor(self.hass, self))
        self.sensors.append(ChargePointCountSensor(self.hass, self))
        self.sensors.append(ChargePointsAvailableSensor(self.hass, self))
        self.sensors.append(ChargePointsUnknownSensor(self.hass, self))
        for i in range(response["numberOfChargePoints"]):
            point_id = response["chargePoints"][i]["evseId"]
            self.binary_sensors.append(
                ChargePointBinarySensor(self.hass, self, point_id, i + 1)
            )


class ChargeStationSensorEntity(SensorEntity):
    """ChargeStationSensorEntity implementation."""

    def __init__(self, hass: HomeAssistant, station: ChargeStation) -> None:
        """Initialize."""
        self.hass: HomeAssistant = hass
        self.station: ChargeStation = station
        self._state: str | None = None
        self._attributes: dict[str, Any] = {}

    @abstractmethod
    def update_from_response(self, response):
        """Update from rest response."""

    def update(self):
        """Update complete station."""
        self.station.update()

    def update_state(self, state: str):
        """Update state."""
        self.native_value = state

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    f"enbw_station_{Utils.generate_entity_id(self.station.station_number)}",
                )
            },
            "name": self.station.name,
            "manufacturer": "EnBW Energie Baden-Württemberg",
        }

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return self._attributes

    def update_attributes(self, attributes: dict[str, Any]):
        """Update attributes."""
        for kvp in attributes:
            self._attributes[kvp] = attributes[kvp]


class ChargeStationBinarySensorEntity(BinarySensorEntity):
    """ChargeStationBinarySensorEntity implementation."""

    def __init__(self, hass: HomeAssistant, station: ChargeStation) -> None:
        """Initialize."""
        self.hass: HomeAssistant = hass
        self.station: ChargeStation = station
        self._attr_is_on = False
        self._attributes: dict[str, Any] = {}

    @abstractmethod
    def update_from_response(self, response):
        """Update from rest response."""

    def update(self):
        """Update complete station."""
        self.station.update()

    def update_state(self, state: bool):
        """Update state."""
        self._attr_is_on = state

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    f"enbw_station_{Utils.generate_entity_id(self.station.station_number)}",
                )
            },
            "name": self.station.name,
            "manufacturer": "EnBW Energie Baden-Württemberg",
        }

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return self._attributes

    def update_attributes(self, attributes: dict[str, Any]):
        """Update attributes."""
        for kvp in attributes:
            self._attributes[kvp] = attributes[kvp]


class ChargePointBinarySensor(ChargeStationBinarySensorEntity):
    """ChargePointBinarySensor implementation."""

    def __init__(
        self, hass: HomeAssistant, station: ChargeStation, point_id: str, index: int
    ) -> None:
        """Initialize."""
        super().__init__(hass, station)
        self.index: int = index
        self.point_id: str = point_id
        self._attr_name = f"{station.name} Charge Point {self.index}"
        self._attr_unique_id = Utils.generate_entity_id(
            f"{station.unique_id}_charge_point_{self.index}"
        )

    def update_from_response(self, response):
        """Update from rest response."""
        state = [x for x in response["chargePoints"] if x["evseId"] == self.point_id]
        if len(state) == 0:
            return
        state = state[0]
        self.update_state(state["status"] != "AVAILABLE")

        plugTypeNames = [connector["plugTypeName"] for connector in state["connectors"]]
        plugTypeCableAttached = [
            connector["cableAttached"] for connector in state["connectors"]
        ]
        plugTypePower = [connector["maxPowerInKw"] for connector in state["connectors"]]

        iconcolor = "primary"
        if state["status"] == "OCCUPIED":
            iconcolor = "gold"
        elif state["status"] == "AVAILABLE":
            iconcolor = "green"
        else:
            iconcolor = "red"

        self.update_attributes(
            {
                ATTR_CABLE_ATTACHED: plugTypeCableAttached,
                ATTR_PLUG_TYPE_NAME: plugTypeNames,
                ATTR_MAX_POWER_IN_KW: plugTypePower,
                ATTR_ADDRESS: response["shortAddress"],
                ATTR_EVSE_ID: state["evseId"],
                ATTR_ICON_COLOR: iconcolor,
                ATTR_UPDATED_AT: datetime.fromtimestamp(
                    self.station.updated_at,
                    tz=timezone.utc,  # noqa: UP017
                ),
            }
        )

    @property
    def translation_key(self):
        """Return Translation Key."""
        return "charge_point"

    @property
    def icon(self) -> str | None:
        """Icon of the entity, based on time."""
        if self.state == "AVAILABLE":
            return "mdi:car-electric-outline"
        return "mdi:car-electric"


class ChargeStationStateBinarySensor(ChargeStationBinarySensorEntity):
    """ChargeStationStateBinarySensor implementation."""

    def __init__(self, hass: HomeAssistant, station: ChargeStation) -> None:
        """Initialize."""
        super().__init__(hass, station)
        self._attr_name = f"{station.name}"
        self._attr_unique_id = Utils.generate_entity_id(f"{station.unique_id}_state")

    @override
    def update_from_response(self, response):
        """Update from rest response."""
        self.update_state(response["availableChargePoints"] > 0)

        plugTypeNames = response["plugTypeNames"]
        plugTypeCableAttached = {}
        plugTypePower = {}

        connectors = []
        for point in response["chargePoints"]:
            for connector in point["connectors"]:
                connectors.append(connector)  # noqa: PERF402

        for typeName in plugTypeNames:
            plugTypeCableAttached[typeName] = any(
                connector["cableAttached"] for connector in connectors
            )
            plugTypePower[typeName] = max(
                connector["maxPowerInKw"] for connector in connectors
            )

        self.update_attributes(
            {
                ATTR_CABLE_ATTACHED: plugTypeCableAttached,
                ATTR_PLUG_TYPE_NAME: plugTypeNames,
                ATTR_MAX_POWER_IN_KW: response["maxPowerInKw"],
                ATTR_MAX_POWER_PER_PLUG_TYPE_IN_KW: plugTypePower,
                ATTR_ADDRESS: response["shortAddress"],
                ATTR_AVAILABLE_CHARGE_POINTS: response["availableChargePoints"],
                ATTR_TOTAL_CHARGE_POINTS: response["numberOfChargePoints"],
                ATTR_UPDATED_AT: datetime.fromtimestamp(
                    self.station.updated_at,
                    tz=timezone.utc,  # noqa: UP017
                ),
            }
        )

    @property
    def translation_key(self):
        """Return Translation Key."""
        return "charge_station"

    @property
    def icon(self) -> str | None:
        """Icon of the entity, based on time."""
        if self.state == "Available":
            return "mdi:car-electric-outline"
        return "mdi:car-electric"


class ChargePointsUnknownSensor(ChargeStationSensorEntity):
    """ChargePointsUnknownSensor implementation."""

    def __init__(self, hass: HomeAssistant, station: ChargeStation) -> None:
        """Initialize."""
        super().__init__(hass, station)
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_name = f"{station.name} Unknown State Charge Points"
        self._attr_unique_id = Utils.generate_entity_id(
            f"{station.unique_id}_unknown_state_charge_points"
        )

    @override
    def update_from_response(self, response):
        """Update from rest response."""
        self.update_state(response["unknownStateChargePoints"])

    @property
    def icon(self) -> str | None:
        """Icon of the entity, based on time."""
        return "mdi:ev-station"


class ChargePointCountSensor(ChargeStationSensorEntity):
    """ChargePointCountSensor implementation."""

    def __init__(self, hass: HomeAssistant, station: ChargeStation) -> None:
        """Initialize."""
        super().__init__(hass, station)
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_name = f"{station.name} Total Charge Points"
        self._attr_unique_id = Utils.generate_entity_id(
            f"{station.unique_id}_total_charge_points"
        )

    @override
    def update_from_response(self, response):
        """Update from rest response."""
        self.update_state(response["numberOfChargePoints"])

    @property
    def icon(self) -> str | None:
        """Icon of the entity, based on time."""
        return "mdi:ev-station"


class ChargePointsAvailableSensor(ChargeStationSensorEntity):
    """ChargePointsAvailableSensor implementation."""

    def __init__(self, hass: HomeAssistant, station: ChargeStation) -> None:
        """Initialize."""
        super().__init__(hass, station)
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_name = f"{station.name} Available Charge Points"
        self._attr_unique_id = Utils.generate_entity_id(
            f"{station.unique_id}_available_charge_points"
        )

    @override
    def update_from_response(self, response):
        """Update from rest response."""
        self.update_state(response["availableChargePoints"])

    @property
    def icon(self) -> str | None:
        """Icon of the entity, based on time."""
        return "mdi:ev-station"
