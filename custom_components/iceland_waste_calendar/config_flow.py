from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HafnarfjordurApi, KopavogurApi, ReykjavikApi, WasteApiError
from .const import (
    CONF_ADDRESS,
    CONF_LOCATION_ID,
    CONF_MUNICIPALITY,
    CONF_POSTAL_CODE,
    DOMAIN,
    MUNICIPALITY_HAFNARFJORDUR,
    MUNICIPALITY_KOPAVOGUR,
    MUNICIPALITY_NAMES,
    MUNICIPALITY_REYKJAVIK,
)
from .postal_codes import POSTAL_CODE_MAP


class IcelandWasteCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._municipality: str = ""
        self._postal_code: str = ""

    # ------------------------------------------------------------------
    # Step 1 — postal code lookup
    # ------------------------------------------------------------------

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            postal_code = user_input[CONF_POSTAL_CODE].strip()
            municipality = POSTAL_CODE_MAP.get(postal_code)

            if municipality is None:
                errors["base"] = "postal_code_not_found"
            elif municipality not in MUNICIPALITY_NAMES:
                errors["base"] = "municipality_not_supported"
            else:
                self._municipality = municipality
                self._postal_code = postal_code
                if municipality == MUNICIPALITY_KOPAVOGUR:
                    return await self.async_step_kopavogur()
                if municipality == MUNICIPALITY_REYKJAVIK:
                    return await self.async_step_reykjavik()
                if municipality == MUNICIPALITY_HAFNARFJORDUR:
                    return await self.async_step_hafnarfjordur()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_POSTAL_CODE): str}),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Kópavogur
    # ------------------------------------------------------------------

    async def async_step_kopavogur(self, user_input=None):
        errors = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip()
            api = KopavogurApi(async_get_clientsession(self.hass))
            try:
                candidates = await api.async_search_locations(address)
                if not candidates:
                    errors["base"] = "cannot_resolve"
                else:
                    loc = candidates[0]
                    await self.async_set_unique_id(f"kopavogur_{loc.id}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Kópavogur - {loc.title}",
                        data={
                            CONF_MUNICIPALITY: MUNICIPALITY_KOPAVOGUR,
                            CONF_POSTAL_CODE: self._postal_code,
                            CONF_ADDRESS: address,
                            CONF_LOCATION_ID: loc.id,
                        },
                    )
            except WasteApiError:
                errors["base"] = "cannot_resolve"
            except Exception:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="kopavogur",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors=errors,
        )

    async def async_step_kopavogur_manual(self, user_input=None):
        errors = {}
        if user_input is not None:
            loc_id = user_input[CONF_LOCATION_ID].strip()
            await self.async_set_unique_id(f"kopavogur_{loc_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Kópavogur - {user_input[CONF_ADDRESS]}",
                data={
                    CONF_MUNICIPALITY: MUNICIPALITY_KOPAVOGUR,
                    CONF_POSTAL_CODE: self._postal_code,
                    CONF_ADDRESS: user_input[CONF_ADDRESS],
                    CONF_LOCATION_ID: loc_id,
                },
            )
        return self.async_show_form(
            step_id="kopavogur_manual",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS): str,
                vol.Required(CONF_LOCATION_ID): str,
            }),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Reykjavík
    # ------------------------------------------------------------------

    async def async_step_reykjavik(self, user_input=None):
        errors = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip()
            api = ReykjavikApi(async_get_clientsession(self.hass))
            try:
                pickups = await api.async_get_pickups(address, self._postal_code)
                if not pickups:
                    errors["base"] = "no_data"
                else:
                    unique_id = f"rvk_{address}_{self._postal_code}".lower().replace(" ", "_")
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Reykjavík - {address}",
                        data={
                            CONF_MUNICIPALITY: MUNICIPALITY_REYKJAVIK,
                            CONF_POSTAL_CODE: self._postal_code,
                            CONF_ADDRESS: address,
                        },
                    )
            except WasteApiError:
                errors["base"] = "cannot_resolve"
            except Exception:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reykjavik",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Hafnarfjörður
    # ------------------------------------------------------------------

    async def async_step_hafnarfjordur(self, user_input=None):
        errors = {}
        if user_input is not None:
            street = user_input[CONF_ADDRESS].strip()
            api = HafnarfjordurApi(async_get_clientsession(self.hass))
            try:
                pickups = await api.async_get_pickups(street)
                if not pickups:
                    errors["base"] = "no_data"
                else:
                    unique_id = f"hafnarfjordur_{street.lower().replace(' ', '_')}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Hafnarfjörður - {street}",
                        data={
                            CONF_MUNICIPALITY: MUNICIPALITY_HAFNARFJORDUR,
                            CONF_POSTAL_CODE: self._postal_code,
                            CONF_ADDRESS: street,
                        },
                    )
            except WasteApiError:
                errors["base"] = "cannot_resolve"
            except Exception:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="hafnarfjordur",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors=errors,
        )
