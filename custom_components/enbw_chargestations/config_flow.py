"""Config flow for Pi Assistant component."""

from __future__ import annotations

from typing import Any

import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow

from .const import API_KEY, DOMAIN, NAME, STATION_NUMBER

_LOGGER = logging.getLogger(__name__)


class EnbwChargeStationsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow ."""

    VERSION = 1

    def generate_schema(self):
        """Geneate Schema."""
        return {
            vol.Required(NAME, default="Charge Station"): str,
            vol.Required(STATION_NUMBER, default="393894"): str,
            vol.Required(
                API_KEY,
                default="d4954e8b2e444fc89a89a463788c0a72",
            ): str,
        }

    def generate_schema_config(self, config_entry: ConfigEntry):
        """Geneate Schema."""
        return {
            vol.Required(
                NAME, default=config_entry.data.get(NAME, "Charge Station")
            ): str,
            vol.Required(
                STATION_NUMBER, default=config_entry.data.get(STATION_NUMBER, "393894")
            ): str,
            vol.Required(
                API_KEY,
                default=config_entry.data.get(
                    API_KEY, "d4954e8b2e444fc89a89a463788c0a72"
                ),
            ): str,
        }

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Reconfigure step."""
        config = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        data_schema = self.generate_schema_config(config)

        errors = {}

        if user_input is not None:
            try:
                self.hass.config_entries.async_update_entry(
                    entry=config, data=user_input
                )
                await self.hass.config_entries.async_reload(config.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unknown exception.")
                errors["base"] = "Unknown exception."

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(data_schema),
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""

        errors = {}

        data_schema = self.generate_schema()

        if user_input is not None:
            try:
                self._async_abort_entries_match(
                    {STATION_NUMBER: user_input[STATION_NUMBER]}
                )
                return self.async_create_entry(
                    title=user_input.get(
                        NAME,
                    ),
                    data=user_input,
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unknown exception.")
                errors["base"] = "Unknown exception."

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))
