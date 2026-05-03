from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KopavogurWasteApi, KopavogurWasteApiError
from .const import CONF_ADDRESS, CONF_LOCATION_ID, DOMAIN

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_ADDRESS): str})
STEP_MANUAL_SCHEMA = vol.Schema({vol.Required(CONF_ADDRESS): str, vol.Required(CONF_LOCATION_ID): str})

class KopavogurWasteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip()
            api = KopavogurWasteApi(async_get_clientsession(self.hass))
            try:
                candidate = await api.async_resolve_address(address)
                await self.async_set_unique_id(f"kopavogur_waste_{candidate.id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Sorphirða - {candidate.title}",
                    data={CONF_ADDRESS: address, CONF_LOCATION_ID: candidate.id},
                )
            except KopavogurWasteApiError:
                errors["base"] = "cannot_resolve"
            except Exception:
                errors["base"] = "unknown"

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    async def async_step_manual(self, user_input=None):
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(f"kopavogur_waste_{user_input[CONF_LOCATION_ID]}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Sorphirða - {user_input[CONF_ADDRESS]}",
                data=user_input,
            )
        return self.async_show_form(step_id="manual", data_schema=STEP_MANUAL_SCHEMA, errors=errors)
