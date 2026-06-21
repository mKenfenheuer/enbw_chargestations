"""Async API client for the EnBW e-mobility public API."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://enbw-emp.azure-api.net/emobility-public-api/api/v1"

DEFAULT_HEADERS = {
    "User-Agent": "Home Assistant",
    "Accept": "application/json",
    "Origin": "https://www.enbw.com",
    "Referer": "https://www.enbw.com/",
}

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15)


class EnbwApiError(Exception):
    """Generic error talking to the EnBW API."""


class EnbwAuthError(EnbwApiError):
    """Raised when the API key is rejected (401/403)."""


class EnbwApiClient:
    """Thin async wrapper around the EnBW charge station endpoints."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        """Initialize the client."""
        self._session = session
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {**DEFAULT_HEADERS, "Ocp-Apim-Subscription-Key": self._api_key}

    async def _get(self, url: str) -> Any:
        try:
            async with self._session.get(
                url, headers=self._headers(), timeout=DEFAULT_TIMEOUT
            ) as response:
                if response.status in (401, 403):
                    raise EnbwAuthError(
                        f"API key rejected (HTTP {response.status})"
                    )
                if response.status >= 400:
                    raise EnbwApiError(
                        f"Unexpected response (HTTP {response.status})"
                    )
                return await response.json()
        except aiohttp.ClientError as err:
            raise EnbwApiError(f"Error communicating with API: {err}") from err
        except TimeoutError as err:
            raise EnbwApiError("Timeout communicating with API") from err

    async def async_get_charge_station(self, station_number: str) -> dict[str, Any]:
        """Return the full detail payload for a single charge station."""
        data = await self._get(f"{API_BASE}/chargestations/{station_number}")
        if not isinstance(data, dict):
            raise EnbwApiError("Unexpected payload for charge station")
        return data

    async def async_get_charge_stations(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
    ) -> list[dict[str, Any]]:
        """Return charge stations within a bounding box."""
        url = (
            f"{API_BASE}/chargestations"
            f"?fromLat={from_lat}&toLat={to_lat}"
            f"&fromLon={from_lon}&toLon={to_lon}"
            "&grouping=false&groupingDivisor=15"
        )
        data = await self._get(url)
        if not isinstance(data, list):
            return []
        return [x for x in data if isinstance(x, dict)]
