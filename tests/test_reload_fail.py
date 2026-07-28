"""Reproduce a config-entry reload of enbw_chargestations when the API fails."""

import aiohttp
from aioresponses import aioresponses
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

STATION_PAYLOAD = {
    "stationId": 393894,
    "shortAddress": "Teststr. 1, 12345 Teststadt",
    "lat": 48.78,
    "lon": 9.18,
    "maxPowerInKw": 150,
    "numberOfChargePoints": 1,
    "availableChargePoints": 1,
    "unknownStateChargePoints": 0,
    "plugTypeNames": ["CCS (Typ 2)"],
    "chargePoints": [
        {
            "evseId": "DE*ENB*E393894001",
            "status": "AVAILABLE",
            "connectors": [
                {"plugTypeName": "CCS (Typ 2)", "cableAttached": True, "maxPowerInKw": 150}
            ],
        }
    ],
}

URL = "https://enbw-emp.azure-api.net/emobility-public-api/api/v1/chargestations/393894"

@pytest.mark.asyncio
async def test_reload_after_connection_error(hass):
    entry = MockConfigEntry(
        domain="enbw_chargestations",
        title="Test Station",
        data={"station_number": "393894", "api_key": "dummy", "name": "Test Station"},
        unique_id="393894",
    )
    entry.add_to_hass(hass)

    with aioresponses() as m:
        m.get(URL, payload=STATION_PAYLOAD, repeat=True)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with aioresponses() as m:
        m.get(URL, exception=aiohttp.ClientConnectionError("boom"), repeat=True)
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    with aioresponses() as m:
        m.get(URL, payload=STATION_PAYLOAD, repeat=True)
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

@pytest.mark.asyncio
async def test_reload_after_auth_error(hass):
    entry = MockConfigEntry(
        domain="enbw_chargestations",
        title="Test Station",
        data={"station_number": "393894", "api_key": "dummy", "name": "Test Station"},
        unique_id="393894",
    )
    entry.add_to_hass(hass)

    with aioresponses() as m:
        m.get(URL, payload=STATION_PAYLOAD, repeat=True)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with aioresponses() as m:
        m.get(URL, status=401, repeat=True)
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        flows = hass.config_entries.flow.async_progress()
