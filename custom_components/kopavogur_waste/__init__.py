from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KopavogurWasteApi
from .const import CONF_ADDRESS, CONF_LOCATION_ID, DEFAULT_SCAN_INTERVAL_HOURS, DOMAIN

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = KopavogurWasteApi(session)
    location_id = entry.data[CONF_LOCATION_ID]

    async def async_update_data():
        try:
            return await api.async_get_pickups(location_id)
        except Exception as err:
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        hass.helpers.event.async_track_time_interval,
        name=f"{DOMAIN}_{location_id}",
        update_method=async_update_data,
        update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "address": entry.data.get(CONF_ADDRESS),
        "location_id": location_id,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
