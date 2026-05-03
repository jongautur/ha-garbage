from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ts_to_date
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    address = data["address"]
    location_id = data["location_id"]

    entities = []
    for item in coordinator.data:
        title = item.get("title", f"Waste {item.get('id')}")
        waste_id = str(item.get("id", title)).lower().replace(" ", "_")
        entities.append(KopavogurWasteNextPickupSensor(coordinator, entry.entry_id, location_id, address, waste_id, title))
        entities.append(KopavogurWasteDaysSensor(coordinator, entry.entry_id, location_id, address, waste_id, title))
    async_add_entities(entities)

class KopavogurWasteBase(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id, location_id, address, waste_id, waste_title):
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._location_id = location_id
        self._address = address
        self._waste_id = waste_id
        self._waste_title = waste_title

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, str(self._location_id))},
            "name": f"Kópavogur sorphirða - {self._address}",
            "manufacturer": "Kópavogur",
            "entry_type": "service",
        }

    def _item(self):
        for item in self.coordinator.data or []:
            if str(item.get("id", item.get("title"))).lower().replace(" ", "_") == self._waste_id:
                return item
        return None

    def _next_ts(self):
        item = self._item()
        if not item:
            return None
        dates = item.get("dates") or []
        if not dates:
            return None
        return dates[0].get("dateFrom")

class KopavogurWasteNextPickupSensor(KopavogurWasteBase):
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, entry_id, location_id, address, waste_id, waste_title):
        super().__init__(coordinator, entry_id, location_id, address, waste_id, waste_title)
        self._attr_name = f"{waste_title} next pickup"
        self._attr_unique_id = f"{entry_id}_{waste_id}_next_pickup"

    @property
    def native_value(self):
        return ts_to_date(self._next_ts())

    @property
    def extra_state_attributes(self):
        item = self._item() or {}
        return {"waste_type": self._waste_title, "location_id": self._location_id, "upcoming": item.get("dates", [])}

class KopavogurWasteDaysSensor(KopavogurWasteBase):
    _attr_native_unit_of_measurement = "d"

    def __init__(self, coordinator, entry_id, location_id, address, waste_id, waste_title):
        super().__init__(coordinator, entry_id, location_id, address, waste_id, waste_title)
        self._attr_name = f"{waste_title} days until pickup"
        self._attr_unique_id = f"{entry_id}_{waste_id}_days_until_pickup"

    @property
    def native_value(self):
        from datetime import date
        date_str = ts_to_date(self._next_ts())
        if not date_str:
            return None
        return (date.fromisoformat(date_str) - date.today()).days
