"""Config flow for Desk Tracker integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DAILY_GOAL,
    CONF_ENTITY_ID,
    CONF_POWER_THRESHOLD,
    DEFAULT_DAILY_GOAL,
    DEFAULT_POWER_THRESHOLD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _validate_entity(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return None if entity exists, or an error key."""
    state = hass.states.get(entity_id)
    if state is None:
        return "entity_not_found"
    return None


class DeskTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            entity_id = user_input[CONF_ENTITY_ID].strip()
            error = _validate_entity(self.hass, entity_id)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Desk Tracker",
                    data={
                        CONF_ENTITY_ID: entity_id,
                        CONF_POWER_THRESHOLD: float(
                            user_input.get(CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD)
                        ),
                        CONF_DAILY_GOAL: float(
                            user_input.get(CONF_DAILY_GOAL, DEFAULT_DAILY_GOAL)
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENTITY_ID): str,
                    vol.Optional(
                        CONF_POWER_THRESHOLD, default=DEFAULT_POWER_THRESHOLD
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_DAILY_GOAL, default=DEFAULT_DAILY_GOAL
                    ): vol.Coerce(float),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return DeskTrackerOptionsFlow(config_entry)


class DeskTrackerOptionsFlow(config_entries.OptionsFlow):
    """Allow reconfiguring after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        current = self._config_entry.data

        if user_input is not None:
            entity_id = user_input[CONF_ENTITY_ID].strip()
            error = _validate_entity(self.hass, entity_id)
            if error:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={
                        CONF_ENTITY_ID: entity_id,
                        CONF_POWER_THRESHOLD: float(
                            user_input.get(CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD)
                        ),
                        CONF_DAILY_GOAL: float(
                            user_input.get(CONF_DAILY_GOAL, DEFAULT_DAILY_GOAL)
                        ),
                    },
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTITY_ID,
                        default=current.get(CONF_ENTITY_ID, ""),
                    ): str,
                    vol.Optional(
                        CONF_POWER_THRESHOLD,
                        default=current.get(CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_DAILY_GOAL,
                        default=current.get(CONF_DAILY_GOAL, DEFAULT_DAILY_GOAL),
                    ): vol.Coerce(float),
                }
            ),
            errors=errors,
        )
