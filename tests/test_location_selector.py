"""Verify the config flow uses a map location selector for the search area."""

from aioresponses import aioresponses
import pytest
import voluptuous as vol
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import LocationSelector
from pytest_homeassistant_custom_component.common import MockConfigEntry

SEARCH_URL_PATTERN = __import__("re").compile(
    r"^https://enbw-emp\.azure-api\.net/emobility-public-api/api/v1/chargestations\?.*"
)
DETAIL_URL = (
    "https://enbw-emp.azure-api.net/emobility-public-api/api/v1/chargestations/393894"
)

STATION = {
    "stationId": 393894,
    "shortAddress": "Teststr. 1",
    "lat": 32.87,
    "lon": -117.22,
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

def _field(schema: vol.Schema, key: str):
    for marker in schema.schema:
        if marker == key:
            return marker, schema.schema[marker]
    raise AssertionError(f"{key} not in schema: {list(schema.schema)}")

@pytest.mark.asyncio
async def test_user_step_offers_location_selector(hass):
    """The form must offer a map picker instead of lat/lon/radius number fields."""
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"]
    keys = [str(marker) for marker in schema.schema]

    assert "latitude" not in keys
    assert "longitude" not in keys
    assert "search_radius" not in keys

    marker, selector = _field(schema, "location")
    assert isinstance(selector, LocationSelector)
    assert selector.config.get("radius") is True

    # Default is pre-filled with the HA home location and the default radius.
    default = marker.default()
    assert default["latitude"] == hass.config.latitude
    assert default["longitude"] == hass.config.longitude
    assert default["radius"] == 10000

@pytest.mark.asyncio
async def test_search_uses_map_radius(hass):
    """The radius picked on the map must drive the search bounding box."""
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )

    with aioresponses() as m:
        m.get(SEARCH_URL_PATTERN, payload=[STATION], repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "location": {
                    "latitude": 48.0,
                    "longitude": 9.0,
                    "radius": 20000,  # 20 km
                },
                "api_key": "dummy",
            },
        )
        requested = [str(url) for (method, url), _ in m.requests.items()]

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "search_station"

    # 20 km radius -> half-extent of 20/2 km in degrees around the picked point.
    half = (1 / 111) * 0.5 * 20
    url = requested[0]
    assert f"fromLat={48.0 - half}" in url
    assert f"toLat={48.0 + half}" in url
    assert f"fromLon={9.0 - half}" in url
    assert f"toLon={9.0 + half}" in url

    # Completing the flow still creates a working entry.
    with aioresponses() as m:
        m.get(DETAIL_URL, payload=STATION, repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"station_number": "393894"}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "station_number": "393894",
        "api_key": "dummy",
        "name": "Teststr. 1",  # derived from the station, not typed
    }
