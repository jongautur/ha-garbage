from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HafnarfjordurApi, KopavogurApi, ReykjavikApi, WasteApiError
from .const import (
    CONF_ADDRESS,
    CONF_LOCATION_ID,
    CONF_MUNICIPALITY,
    CONF_POSTAL_CODE,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    MUNICIPALITY_HAFNARFJORDUR,
    MUNICIPALITY_KOPAVOGUR,
    MUNICIPALITY_REYKJAVIK,
    MUNICIPALITY_NAMES,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    municipality = entry.data[CONF_MUNICIPALITY]
    address = entry.data.get(CONF_ADDRESS, "")

    if municipality == MUNICIPALITY_KOPAVOGUR:
        api = KopavogurApi(session)
        location_id = entry.data[CONF_LOCATION_ID]
        device_id = f"kopavogur_{location_id}"

        async def async_update_data():
            try:
                return await api.async_get_pickups(location_id)
            except WasteApiError as err:
                raise UpdateFailed(str(err)) from err

    elif municipality == MUNICIPALITY_REYKJAVIK:
        api = ReykjavikApi(session)
        postal_code = entry.data[CONF_POSTAL_CODE]
        device_id = f"rvk_{address}_{postal_code}".lower().replace(" ", "_")

        async def async_update_data():
            try:
                return await api.async_get_pickups(address, postal_code)
            except WasteApiError as err:
                raise UpdateFailed(str(err)) from err

    elif municipality == MUNICIPALITY_HAFNARFJORDUR:
        api = HafnarfjordurApi(session)
        device_id = f"hfj_{address.lower().replace(' ', '_')}"

        async def async_update_data():
            try:
                return await api.async_get_pickups(address)
            except WasteApiError as err:
                raise UpdateFailed(str(err)) from err

    else:
        _LOGGER.error("Unknown municipality: %s", municipality)
        return False

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{device_id}",
        update_method=async_update_data,
        update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "municipality": municipality,
        "municipality_name": MUNICIPALITY_NAMES.get(municipality, municipality),
        "address": address,
        "device_id": device_id,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
