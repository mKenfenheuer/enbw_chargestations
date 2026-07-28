"""The station picker is a searchable dropdown."""

import re

from aioresponses import aioresponses
import pytest
from homeassistant.helpers.selector import SelectSelector, SelectSelectorMode

BASE = "https://enbw-emp.azure-api.net/emobility-public-api/api/v1/chargestations"
SEARCH_URL = re.compile(rf"^{re.escape(BASE)}\?.*")

USER_INPUT = {
    "location": {"latitude": 48.0, "longitude": 9.0, "radius": 10000},
    "api_key": "dummy",
}

def _station(number: int, address: str) -> dict:
    return {
        "stationId": number,
        "shortAddress": address,
        "lat": 48.0,
        "lon": 9.0,
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

@pytest.mark.asyncio
async def test_station_picker_is_a_dropdown(hass):
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )

    stations = [_station(100 + i, f"Teststr. {i}") for i in range(12)]
    with aioresponses() as m:
        m.get(SEARCH_URL, payload=stations, repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["step_id"] == "search_station"
    selector = next(
        value
        for marker, value in result["data_schema"].schema.items()
        if str(marker) == "station_number"
    )
    assert isinstance(selector, SelectSelector)

    assert selector.config["mode"] == SelectSelectorMode.DROPDOWN.value
    assert selector.config["multiple"] is False
    # Labels carry address, distance and power, so typing any of them filters.
    assert len(selector.config["options"]) == 12
    assert "Teststr." in selector.config["options"][0]["label"]

@pytest.mark.asyncio
async def test_dropdown_selection_still_creates_the_entry(
    hass
):
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )

    stations = [_station(111, "Bahnhofstr. 1"), _station(222, "Hauptstr. 9")]
    with aioresponses() as m:
        m.get(SEARCH_URL, payload=stations, repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    with aioresponses() as m:
        m.get(f"{BASE}/222", payload=stations[1], repeat=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"station_number": "222"}
        )
        await hass.async_block_till_done()

    assert result["type"].value == "create_entry"
    assert result["title"] == "Hauptstr. 9"
