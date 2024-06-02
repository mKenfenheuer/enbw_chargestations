"""Charge station sensor implementation"""

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .charge_station import ChargeStation

from .const import API_KEY, DOMAIN, NAME, STATION_NUMBER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:  # pylint disable=unused-argument
    """Set up EnBw Charge station via config entry."""
    station: ChargeStation = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(station.binary_sensors)
