"""The search offers up to 50 of the nearest stations."""

import re

from aioresponses import aioresponses
import pytest

BASE = "https://enbw-emp.azure-api.net/emobility-public-api/api/v1/chargestations"
SEARCH_URL = re.compile(rf"^{re.escape(BASE)}\?.*")

# hass.config home location used by the test harness.
HOME_LAT = 32.87336
HOME_LON = -117.22743

USER_INPUT = {
    "location": {"latitude": HOME_LAT, "longitude": HOME_LON, "radius": 50000},
    "api_key": "dummy",
}

def _station(number: int, lat: float, lon: float) -> dict:
    return {
        "stationId": number,
        "shortAddress": f"Teststr. {number}",
        "lat": lat,
        "lon": lon,
        "maxPowerInKw": 150,
        "numberOfChargePoints": 1,
        "availableChargePoints": 1,
        "unknownStateChargePoints": 0,
        "plugTypeNames": ["CCS (Typ 2)"],
        "chargePoints": [
            {
                "evseId": f"DE*ENB*E{number}001",
                "status": "AVAILABLE",
                "connectors": [
                    {
                        "plugTypeName": "CCS (Typ 2)",
                        "cableAttached": True,
                        "maxPowerInKw": 150,
                    }
                ],
            }
        ],
    }


async def _options_for(hass, stations):
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )
    with aioresponses() as m:
        m.get(SEARCH_URL, payload=stations, repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["step_id"] == "search_station", result
    selector = next(
        value
        for marker, value in result["data_schema"].schema.items()
        if str(marker) == "station_number"
    )
    return selector.config["options"]

@pytest.mark.asyncio
async def test_more_than_fifteen_results_are_offered(hass):
    """The old cap of 15 is gone."""
    stations = [
        _station(1000 + i, HOME_LAT + i * 0.001, HOME_LON) for i in range(30)
    ]
    options = await _options_for(hass, stations)
    assert len(options) == 30

@pytest.mark.asyncio
async def test_results_are_capped_at_fifty(hass):
    stations = [
        _station(1000 + i, HOME_LAT + i * 0.001, HOME_LON) for i in range(80)
    ]
    options = await _options_for(hass, stations)
    assert len(options) == 50

@pytest.mark.asyncio
async def test_the_nearest_fifty_are_kept(hass):
    """Cutting to 50 must keep the closest ones, not the first 50 returned."""
    # Deliberately hand the API response back farthest-first.
    stations = [
        _station(1000 + i, HOME_LAT + (80 - i) * 0.001, HOME_LON) for i in range(80)
    ]
    options = await _options_for(hass, stations)
    values = [option["value"] for option in options]


    # Station 1079 sits closest to home, 1000 farthest.
    assert values[0] == "1079"
    assert len(values) == 50
    # The 30 farthest stations must have been dropped.
    assert "1000" not in values
    assert values[-1] == "1030"
