"""Config flow for the Tuya Valve (Cloud Minimal) integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult

from .client import TuyaValveClient
from .const import (
    CONF_BASE_URL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_SEC,
    DOMAIN,
)


class TuyaValveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the interactive setup flow for Tuya Valve."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Ask for Tuya Cloud credentials + device id, validate, and create the entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = TuyaValveClient(
                base=user_input[CONF_BASE_URL],
                client_id=user_input[CONF_CLIENT_ID],
                client_secret=user_input[CONF_CLIENT_SECRET],
                device_id=user_input[CONF_DEVICE_ID],
            )
            ok = await self.hass.async_add_executor_job(client.validate)
            if not ok:
                errors["base"] = "auth_failed"
            else:
                # Fetch device name for entry title
                name = await self.hass.async_add_executor_job(client.device_name)
                title = name or f"Tuya Valve ({user_input[CONF_DEVICE_ID][-6:]})"

                await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                vol.Required(CONF_CLIENT_ID): str,
                vol.Required(CONF_CLIENT_SECRET): str,
                vol.Required(CONF_DEVICE_ID): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Support YAML import by delegating to the same user step."""
        return await self.async_step_user(user_input)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return TuyaValveOptionsFlow(config_entry)


class TuyaValveOptionsFlow(config_entries.OptionsFlow):
    """Single-page options flow (currently just scan interval)."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Store the config entry so we can read/write options."""
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Show and process the options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    "scan_interval",
                    default=self.entry.options.get("scan_interval", DEFAULT_SCAN_SEC),
                ): int
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
