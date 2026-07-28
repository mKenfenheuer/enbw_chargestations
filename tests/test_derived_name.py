"""The entry name is derived from the station, not typed by the user."""

import re

from aioresponses import aioresponses
import pytest
from homeassistant.data_entry_flow import FlowResultType

BASE = "https://enbw-emp.azure-api.net/emobility-public-api/api/v1/chargestations"
SEARCH_URL = re.compile(rf"^{re.escape(BASE)}\?.*")

def _station(number: int, address: str | None) -> dict:
    payload = {
        "stationId": number,
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
    if address is not None:
        payload["shortAddress"] = address
    return payload


USER_INPUT = {
    "location": {"latitude": 48.0, "longitude": 9.0, "radius": 10000},
    "api_key": "dummy",
}

@pytest.mark.asyncio
async def test_user_step_has_no_name_field(hass):
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )
    keys = [str(marker) for marker in result["data_schema"].schema]
    assert "name" not in keys

@pytest.mark.asyncio
async def test_name_derived_from_selected_search_result(
    hass
):
    """Picking a station from the map search names the entry after it."""
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )

    stations = [
        _station(111, "Bahnhofstr. 1, Karlsruhe"),
        _station(222, "Hauptstr. 9, Mannheim"),
    ]
    with aioresponses() as m:
        m.get(SEARCH_URL, payload=stations, repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["step_id"] == "search_station"

    with aioresponses() as m:
        m.get(f"{BASE}/222", payload=stations[1], repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"station_number": "222"}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hauptstr. 9, Mannheim"
    assert result["data"] == {
        "station_number": "222",
        "api_key": "dummy",
        "name": "Hauptstr. 9, Mannheim",
    }

@pytest.mark.asyncio
async def test_name_falls_back_without_address(hass):
    """A station without an address still gets a usable name."""
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )

    station = _station(333, None)
    with aioresponses() as m:
        m.get(SEARCH_URL, payload=[station], repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["step_id"] == "search_station"

    with aioresponses() as m:
        m.get(f"{BASE}/333", payload=station, repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"station_number": "333"}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Charge station 333"
