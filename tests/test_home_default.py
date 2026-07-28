"""The map starts at the Home Assistant home location."""

import pytest

@pytest.mark.asyncio
async def test_marker_starts_at_configured_home(hass):
    """Set a distinctive home location and check the marker default follows it."""
    await hass.config.async_update(latitude=48.7758, longitude=9.1829)

    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )
    marker = next(m for m in result["data_schema"].schema if str(m) == "location")
    default = marker.default()

    assert default["latitude"] == 48.7758
    assert default["longitude"] == 9.1829
    assert default["radius"] == 10000

@pytest.mark.asyncio
async def test_marker_follows_a_moved_home(hass):
    """Moving the home location moves the starting point of a new flow too."""
    await hass.config.async_update(latitude=52.5200, longitude=13.4050)
    result = await hass.config_entries.flow.async_init(
        "enbw_chargestations", context={"source": "user"}
    )
    marker = next(m for m in result["data_schema"].schema if str(m) == "location")
    assert marker.default()["latitude"] == 52.5200
    assert marker.default()["longitude"] == 13.4050
