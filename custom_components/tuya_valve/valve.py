"""Valve platform for the Tuya Valve (Cloud Minimal) integration.

Creates a ValveEntity backed by Tuya Cloud requests. We poll only the ON/OFF
state via the update coordinator. Static device metadata (name, model, MAC, SN)
is fetched once at setup and exposed via device_info and attributes.
"""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,  # for MAC in device_info
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .client import TuyaValveClient
from .const import (
    CONF_BASE_URL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    DEFAULT_SCAN_SEC,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the valve entity from a config entry.

    Fetch Tuya device metadata once (no periodic polling) and build a
    DataUpdateCoordinator that polls only the valve open/closed state.
    """
    data = entry.data

    client = TuyaValveClient(
        base=data[CONF_BASE_URL],
        client_id=data[CONF_CLIENT_ID],
        client_secret=data[CONF_CLIENT_SECRET],
        device_id=data[CONF_DEVICE_ID],
    )

    # One-shot metadata fetch (no periodic polling)
    meta = await hass.async_add_executor_job(client.device_meta)
    # Prefer cloud name if present; otherwise fall back to entry title
    friendly_name = (meta or {}).get("name") or entry.title

    async def _async_update():
        """Return current valve state: True=open, False=closed, None=unknown."""
        return await hass.async_add_executor_job(client.state)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_coordinator",
        update_method=_async_update,
        update_interval=timedelta(
            seconds=entry.options.get("scan_interval", DEFAULT_SCAN_SEC)
        ),
    )

    await coordinator.async_config_entry_first_refresh()
    async_add_entities(
        [TuyaValveEntity(client, coordinator, friendly_name, data[CONF_DEVICE_ID], meta)]
    )


class TuyaValveEntity(CoordinatorEntity, ValveEntity):
    """Valve entity that opens/closes a Tuya water valve via Tuya Cloud."""

    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_reports_position = False
    _attr_device_class = ValveDeviceClass.WATER

    def __init__(
        self,
        client: TuyaValveClient,
        coordinator: DataUpdateCoordinator,
        name: str,
        device_id: str,
        meta: dict | None,
    ) -> None:
        """Store client, metadata, and coordinator for this valve instance."""
        super().__init__(coordinator)
        self._client = client
        self._attr_name = name
        self._device_id = device_id
        self._meta = meta or {}
        self._attr_unique_id = f"tuya_valve_{device_id}"

    @property
    def is_closed(self) -> bool | None:
        """Return True if the valve is closed, False if open, or None if unknown."""
        state = self.coordinator.data  # True means flow is ON/open
        if state is None:
            return None
        return not state

    @property
    def available(self) -> bool:
        """Return True if the last coordinator update produced a state."""
        return self.coordinator.data is not None

    @property
    def device_info(self):
        """Return static details for the Device Registry (shown on the device page)."""
        mac = self._meta.get("mac")
        model = self._meta.get("model") or self._meta.get("product_name")
        serial = self._meta.get("sn")
        name = self._meta.get("name") or self.name

        info = {
            "identifiers": {("tuya_valve", self._device_id)},
            "manufacturer": "Tuya",
            "model": model or "Remote Water Valve",
            "name": name,
            "serial_number": serial,
        }
        if mac:
            # expose MAC as a device connection tuple
            info["connections"] = {(CONNECTION_NETWORK_MAC, mac)}
        return info

    @property
    def extra_state_attributes(self):
        """Expose Tuya identifiers as static entity attributes (no polling)."""
        return {
            "tuya_device_id": self._device_id,
            "tuya_mac": self._meta.get("mac"),
            "tuya_sn": self._meta.get("sn"),
            "tuya_category": self._meta.get("category"),
            "tuya_product_name": self._meta.get("product_name"),
            "tuya_product_id": self._meta.get("product_id"),
            "tuya_model": self._meta.get("model"),
        }

    async def async_open_valve(self) -> None:
        """Command the valve to open, then refresh state."""
        ok = await self.hass.async_add_executor_job(self._client.turn_on)
        if ok:
            await self.coordinator.async_request_refresh()

    async def async_close_valve(self) -> None:
        """Command the valve to close, then refresh state."""
        ok = await self.hass.async_add_executor_job(self._client.turn_off)
        if ok:
            await self.coordinator.async_request_refresh()
