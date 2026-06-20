"""One sensor per child × activity. State = layer summary; attributes hold the
full recommendation (clothing, accessories, safety, weather)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify

from .const import (
    DOMAIN, CONF_ACTIVITIES, CONF_BIRTHDATE,
    DEFAULT_ACTIVITIES_BABY, DEFAULT_ACTIVITIES_CHILD,
)
from .engine import ACTIVITIES, Weather, make_child, recommend


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    if discovery_info is None:
        return
    data = hass.data[DOMAIN]
    coordinator = data["coordinator"]
    today = dt_util.now().date()

    entities = []
    for child_conf in data["children"]:
        child = make_child(child_conf[CONF_NAME], child_conf[CONF_BIRTHDATE], today)
        activities = child_conf.get(CONF_ACTIVITIES) or (
            DEFAULT_ACTIVITIES_CHILD if child.catalog == "child"
            else DEFAULT_ACTIVITIES_BABY)
        for key in activities:
            entities.append(
                SpacerekSensor(coordinator, data, child_conf, ACTIVITIES[key]))
    async_add_entities(entities)


class SpacerekSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:tshirt-crew"
    _attr_has_entity_name = False

    def __init__(self, coordinator, data, child_conf, activity) -> None:
        super().__init__(coordinator)
        self._data = data
        self._child_conf = child_conf
        self._activity = activity
        name = child_conf[CONF_NAME]
        self._attr_name = f"Spacerek {name} – {activity.label}"
        self._attr_unique_id = f"{DOMAIN}_{slugify(name)}_{activity.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, slugify(name))},
            name=f"Spacerek: {name}",
            manufacturer="Spacerek",
        )

    def _build(self):
        weather = self.coordinator.data or Weather()
        today = dt_util.now().date()
        child = make_child(
            self._child_conf[CONF_NAME], self._child_conf[CONF_BIRTHDATE], today)
        return recommend(child, self._activity, weather,
                         car_cabin=self._data["car_cabin"])

    @callback
    def _handle_coordinator_update(self) -> None:
        rec = self._build()
        self._attr_native_value = rec.summary[:255]
        self._attr_extra_state_attributes = {
            "naglowek": rec.headline,
            "ubior": rec.layers,
            "akcesoria": rec.accessories,
            "uwagi": rec.safety,
            "poziom_ciepla": rec.warmth_level,
            "wiek": rec.child["wiek"],
            "rodzaj": rec.activity["nazwa"],
            **{f"pogoda_{k}": v for k, v in rec.weather.items()},
        }
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()
