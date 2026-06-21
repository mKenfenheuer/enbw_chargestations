"""Diagnostics support for the EnBW charge stations integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import API_KEY
from .coordinator import EnbwConfigEntry

TO_REDACT = {API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EnbwConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "data": coordinator.data,
    }
