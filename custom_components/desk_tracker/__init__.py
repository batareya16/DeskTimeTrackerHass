"""Desk Tracker — track time at your desk via a smart plug power sensor."""
from __future__ import annotations

import logging
import os

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

_CARD_URL = f"/{DOMAIN}/desk-tracker-card.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the Lovelace card as a static resource."""
    card_path = os.path.join(
        hass.config.path("custom_components"), DOMAIN, "www", "desk-tracker-card.js"
    )

    if not os.path.isfile(card_path):
        _LOGGER.warning("Desk Tracker: card file not found at %s", card_path)
        return True

    await hass.http.async_register_static_paths(
        [StaticPathConfig(_CARD_URL, card_path, cache_headers=False)]
    )
    add_extra_js_url(hass, _CARD_URL)
    _LOGGER.debug("Desk Tracker: registered card at %s", _CARD_URL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Desk Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
