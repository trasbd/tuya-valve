"""Tuya Valve (Cloud Minimal) integration.

Exposes a ValveEntity controlled via Tuya Cloud (v2 canonical signing).
Setup hands off to platform(s) declared in PLATFORMS.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration’s platforms for a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
