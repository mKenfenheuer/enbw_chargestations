"""The add dialog no longer asks for a station number."""

import re

from aioresponses import aioresponses
import pytest
from homeassistant.data_entry_flow import FlowResultType

SEARCH_URL = re.compile(
    r"^https://enbw-emp\.azure-api\.net/emobility-public-api/api/v1/chargestations\?.*"
)
DETAIL = "https://enbw-emp.azure-api.net/emobility-public-api/api/v1/chargestations/222"

def _station(number: int, address: str) -> dict:
    return {
        "stationId": number,
        "shortAddress": address,
        "lat": 32.87,
        "lon": -117.22,
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


USER_INPUT = {
    "location": {"latitude": 48.0, "longitude": 9.0, "radius": 10000},
    "api_key": "dummy",
}

@pytest.mark.asyncio
async def test_user_step_only_asks_for_area_and_key(hass):
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )
    keys = [str(marker) for marker in result["data_schema"].schema]
    # The API key is asked for first, the search area map below it.
    assert keys == ["api_key", "location"]

@pytest.mark.asyncio
async def test_flow_always_goes_through_the_map_search(
    hass
):
    """Without a station number field, the search step is the only way in."""
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )

    stations = [_station(111, "Bahnhofstr. 1"), _station(222, "Hauptstr. 9")]
    with aioresponses() as m:
        m.get(SEARCH_URL, payload=stations, repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "search_station"

    with aioresponses() as m:
        m.get(DETAIL, payload=stations[1], repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"station_number": "222"}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "station_number": "222",
        "api_key": "dummy",
        "name": "Hauptstr. 9",
    }

@pytest.mark.asyncio
async def test_empty_search_reports_error(hass):
    """An area with no stations must surface an error, not a dead end."""
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )

    with aioresponses() as m:
        m.get(SEARCH_URL, payload=[], repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_stations_found"}

@pytest.mark.asyncio
async def test_reconfigure_still_takes_a_station_number(
    hass
):
    """The escape hatch for a specific station lives in reconfigure now."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain="enbw_chargestations",
        title="Hauptstr. 9",
        data={"station_number": "222", "api_key": "dummy", "name": "Hauptstr. 9"},
        unique_id="222",
    )
    entry.add_to_hass(hass)

    with aioresponses() as m:
        m.get(DETAIL, payload=_station(222, "Hauptstr. 9"), repeat=True)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations",
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )
    keys = [str(marker) for marker in result["data_schema"].schema]
    assert "station_number" in keys
