"""Reproduce a config-entry reload of the enbw_chargestations integration."""

import asyncio
import logging
import sys

from aioresponses import aioresponses
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

logging.basicConfig(level=logging.DEBUG)

STATION_PAYLOAD = {
    "stationId": 393894,
    "shortAddress": "Teststr. 1, 12345 Teststadt",
    "lat": 48.78,
    "lon": 9.18,
    "maxPowerInKw": 150,
    "numberOfChargePoints": 2,
    "availableChargePoints": 1,
    "unknownStateChargePoints": 0,
    "plugTypeNames": ["CCS (Typ 2)"],
    "chargePoints": [
        {
            "evseId": "DE*ENB*E393894001",
            "status": "AVAILABLE",
            "connectors": [
                {
                    "plugTypeName": "CCS (Typ 2)",
                    "cableAttached": True,
                    "maxPowerInKw": 150,
                }
            ],
        },
        {
            "evseId": "DE*ENB*E393894002",
            "status": "OCCUPIED",
            "connectors": [
                {
                    "plugTypeName": "CCS (Typ 2)",
                    "cableAttached": True,
                    "maxPowerInKw": 150,
                }
            ],
        },
    ],
}

@pytest.mark.asyncio
async def test_reload(hass):
    entry = MockConfigEntry(
        domain="enbw_chargestations",
        title="Test Station",
        data={
            "station_number": "393894",
            "api_key": "dummy",
            "name": "Test Station",
        },
        unique_id="393894",
    )
    entry.add_to_hass(hass)

    with aioresponses() as m:
        m.get(
            "https://enbw-emp.azure-api.net/emobility-public-api/api/v1/chargestations/393894",
            payload=STATION_PAYLOAD,
            repeat=True,
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state.value == "loaded"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s", "-p", "no:cacheprovider"]))
