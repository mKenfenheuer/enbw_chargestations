"""Verify opening-hours sensors and their effect on availability."""

from aioresponses import aioresponses
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

URL = "https://api.emp.emob-enbw.com/emobility-public-api/api/v1/chargestations/1157303"

CLOSED_PAYLOAD = {
    "stationId": 1157303,
    "shortAddress": "Jakobstraße 57, 51465 Bergisch Gladbach, DE",
    "lat": 50.99265,
    "lon": 7.11857,
    "maxPowerInKw": 300,
    "numberOfChargePoints": 1,
    "availableChargePoints": 1,
    "unknownStateChargePoints": 0,
    "alwaysOpen": False,
    "openingHours": "Mo: 08:00 - 20:00",
    "openingTimes": {
        "regularHours": [{"weekDays": [1], "periods": [{"begin": "08:00", "end": "20:00"}]}],
        "twentyFourSeven": False,
        "closedOnHolidays": True,
        "nextOpeningTime": "2026-10-12T08:00:00+02:00",
    },
    "plugTypeNames": ["CCS (Typ 2)"],
    "chargePoints": [
        {
            "evseId": "DE*EBW*E910608*1",
            "status": "AVAILABLE",
            "connectors": [
                {"plugTypeName": "CCS (Typ 2)", "cableAttached": True, "maxPowerInKw": 300}
            ],
        }
    ],
}

OPEN_24_7_PAYLOAD = {
    **CLOSED_PAYLOAD,
    "alwaysOpen": True,
    "openingHours": None,
    "openingTimes": {"regularHours": [], "twentyFourSeven": True},
}


async def _setup(hass, payload):
    entry = MockConfigEntry(
        domain="enbw_chargestations",
        title="Test Station",
        data={"station_number": "1157303", "api_key": "dummy", "name": "Test Station"},
        unique_id="1157303",
    )
    entry.add_to_hass(hass)
    with aioresponses() as m:
        m.get(URL, payload=payload, repeat=True)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_closed_station_is_not_reported_as_available(hass):
    """A station with free charge points but closed opening hours must not read 'available'."""
    await _setup(hass, CLOSED_PAYLOAD)

    assert hass.states.get("binary_sensor.test_station_open_now").state == "off"
    assert hass.states.get("binary_sensor.test_station_availability").state == "off"
    assert hass.states.get("sensor.test_station_next_closing_time").state == "unknown"
    assert hass.states.get("sensor.test_station_next_opening_time").state != "unknown"
    assert (
        hass.states.get("binary_sensor.test_station_charge_point_1_300_kw").state
        == "on"
    )


@pytest.mark.asyncio
async def test_24_7_station_with_free_point_is_available(hass):
    """A 24/7 station with a free charge point must read 'available' as before."""
    await _setup(hass, OPEN_24_7_PAYLOAD)

    assert hass.states.get("binary_sensor.test_station_open_now").state == "on"
    assert hass.states.get("binary_sensor.test_station_availability").state == "on"
    assert (
        hass.states.get("binary_sensor.test_station_charge_point_1_300_kw").state
        == "off"
    )
    # A 24/7 station never closes or opens, so the API omits both timestamps.
    assert hass.states.get("sensor.test_station_next_opening_time").state == "unknown"
    assert hass.states.get("sensor.test_station_next_closing_time").state == "unknown"
