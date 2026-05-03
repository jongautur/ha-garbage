from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    municipality_name = data["municipality_name"]
    address = data["address"]
    device_id = data["device_id"]

    entities = []
    for item in coordinator.data:
        waste_id = item["id"]
        title = item["title"]
        entities.append(
            WasteNextPickupSensor(coordinator, entry.entry_id, device_id, municipality_name, address, waste_id, title)
        )
        entities.append(
            WasteDaysSensor(coordinator, entry.entry_id, device_id, municipality_name, address, waste_id, title)
        )
    async_add_entities(entities)


class WasteBase(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id, device_id, municipality_name, address, waste_id, waste_title):
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._device_id = device_id
        self._municipality_name = municipality_name
        self._address = address
        self._waste_id = waste_id
        self._waste_title = waste_title

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": f"{self._municipality_name} sorphirða - {self._address}",
            "manufacturer": self._municipality_name,
            "entry_type": "service",
        }

    def _item(self) -> dict | None:
        for item in self.coordinator.data or []:
            if item.get("id") == self._waste_id:
                return item
        return None


class WasteNextPickupSensor(WasteBase):
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, entry_id, device_id, municipality_name, address, waste_id, waste_title):
        super().__init__(coordinator, entry_id, device_id, municipality_name, address, waste_id, waste_title)
        self._attr_name = waste_title
        self._attr_unique_id = f"{entry_id}_{waste_id}_next_pickup"

    @property
    def native_value(self) -> date | None:
        item = self._item()
        if not item or not item.get("next_dates"):
            return None
        try:
            return date.fromisoformat(item["next_dates"][0])
        except (ValueError, IndexError):
            return None

    @property
    def extra_state_attributes(self):
        item = self._item() or {}
        return {
            "waste_type": self._waste_title,
            "upcoming": item.get("next_dates", []),
        }


class WasteDaysSensor(WasteBase):
    _attr_native_unit_of_measurement = "d"

    def __init__(self, coordinator, entry_id, device_id, municipality_name, address, waste_id, waste_title):
        super().__init__(coordinator, entry_id, device_id, municipality_name, address, waste_id, waste_title)
        self._attr_name = f"{waste_title} - dagar"
        self._attr_unique_id = f"{entry_id}_{waste_id}_days"

    @property
    def native_value(self) -> int | None:
        item = self._item()
        if not item or not item.get("next_dates"):
            return None
        try:
            return (date.fromisoformat(item["next_dates"][0]) - date.today()).days
        except (ValueError, IndexError):
            return None
