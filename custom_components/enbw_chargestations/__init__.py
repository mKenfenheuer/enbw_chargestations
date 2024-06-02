"""Custom integration for Pi Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .charge_station import ChargeStation
from .const import API_KEY, DOMAIN, NAME, STATION_NUMBER

PLATFORMS: list[str] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:  # pylint: disable=unused-argument
    """Remove a config entry from a device."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up entities."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][config_entry.entry_id] = ChargeStation(
        hass,
        config_entry.data.get(NAME),
        config_entry.data.get(STATION_NUMBER),
        config_entry.data.get(API_KEY),
    )
    await hass.async_add_executor_job(hass.data[DOMAIN][config_entry.entry_id].update)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
