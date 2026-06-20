"""Spacerek — child clothing recommendations for Home Assistant.

YAML setup: builds a weather coordinator, creates one sensor per child×activity,
and registers the ``spacerek.recommend`` action (returns structured response).
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.core import (
    HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN, CONF_SOURCES, CONF_CHILDREN, CONF_BIRTHDATE, CONF_ACTIVITIES,
    CONF_CAR_CABIN, DEFAULT_SOURCES, DEFAULT_CAR_CABIN_TEMP,
)
from .coordinator import SpacerekCoordinator, async_build_weather
from .engine import ACTIVITIES, make_child, recommend

CONF_CHILD = "child"
CONF_ACTIVITY = "activity"
CONF_DAY = "day"
CONF_TEMPERATURE = "temperature"
CONF_FEELS_LIKE = "feels_like"

SOURCES_SCHEMA = vol.Schema(
    {vol.Optional(key): cv.entity_id for key in DEFAULT_SOURCES}
)

CHILD_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_BIRTHDATE): cv.date,
    vol.Optional(CONF_ACTIVITIES): vol.All(cv.ensure_list, [vol.In(ACTIVITIES)]),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_SOURCES, default=dict): SOURCES_SCHEMA,
        vol.Required(CONF_CHILDREN): vol.All(cv.ensure_list, [CHILD_SCHEMA]),
        vol.Optional(CONF_CAR_CABIN, default=DEFAULT_CAR_CABIN_TEMP): vol.Coerce(float),
    }),
}, extra=vol.ALLOW_EXTRA)

RECOMMEND_SCHEMA = vol.Schema({
    vol.Optional(CONF_CHILD): cv.string,
    vol.Required(CONF_ACTIVITY): vol.In(ACTIVITIES),
    vol.Optional(CONF_DAY, default="today"): vol.In(["today", "tomorrow"]),
    vol.Optional(CONF_TEMPERATURE): vol.Coerce(float),
    vol.Optional(CONF_FEELS_LIKE): vol.Coerce(float),
})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    conf = config[DOMAIN]
    # Merge over defaults so an omitted/partial `sources:` block can't crash setup.
    sources = {**DEFAULT_SOURCES, **conf[CONF_SOURCES]}
    car_cabin = conf[CONF_CAR_CABIN]

    coordinator = SpacerekCoordinator(hass, sources)
    coordinator.async_setup_listeners()   # before refresh: don't miss the populate event
    await coordinator.async_refresh()

    hass.data[DOMAIN] = {
        "coordinator": coordinator,
        "sources": sources,
        "car_cabin": car_cabin,
        "children": conf[CONF_CHILDREN],
    }

    async def handle_recommend(call: ServiceCall) -> ServiceResponse:
        data = hass.data[DOMAIN]
        activity = ACTIVITIES[call.data[CONF_ACTIVITY]]
        weather = await async_build_weather(
            hass, data["sources"], call.data[CONF_DAY])
        if CONF_TEMPERATURE in call.data:
            weather.temp = call.data[CONF_TEMPERATURE]
        if CONF_FEELS_LIKE in call.data:
            weather.feels_like = call.data[CONF_FEELS_LIKE]

        today = dt_util.now().date()
        wanted = call.data.get(CONF_CHILD)
        results = {}
        for child_conf in data["children"]:
            name = child_conf[CONF_NAME]
            if wanted and name.lower() != wanted.lower():
                continue
            child = make_child(name, child_conf[CONF_BIRTHDATE], today)
            rec = recommend(child, activity, weather, car_cabin=data["car_cabin"])
            results[name] = rec.to_dict()
        return {"recommendations": results}

    hass.services.async_register(
        DOMAIN, "recommend", handle_recommend,
        schema=RECOMMEND_SCHEMA, supports_response=SupportsResponse.ONLY,
    )

    hass.async_create_task(
        async_load_platform(hass, "sensor", DOMAIN, {}, config))
    return True
