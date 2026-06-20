"""Reads the configured weather entities (and a daily forecast) into a
``Weather`` snapshot the engine can consume."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN, SRC_TEMPERATURE, SRC_FEELS_LIKE, SRC_RAIN, SRC_SNOW, SRC_UV,
    SRC_WIND, SRC_GUST, SRC_CLOUD, SRC_AQI, SRC_CONDITION, SRC_FORECAST,
)
from .engine import Weather

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=15)
_UNAVAILABLE = (None, "", "unknown", "unavailable")


def _num(hass: HomeAssistant, entity_id: str):
    state = hass.states.get(entity_id) if entity_id else None
    if state is None or state.state in _UNAVAILABLE:
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return None


def _text(hass: HomeAssistant, entity_id: str):
    state = hass.states.get(entity_id) if entity_id else None
    if state is None or state.state in _UNAVAILABLE:
        return None
    return state.state


async def async_build_weather(hass: HomeAssistant, sources: dict,
                              day: str = "today") -> Weather:
    """Build a Weather snapshot from live states + a daily forecast."""
    w = Weather(
        temp=_num(hass, sources[SRC_TEMPERATURE]),
        feels_like=_num(hass, sources[SRC_FEELS_LIKE]),
        rain_rate=_num(hass, sources[SRC_RAIN]),
        snow_rate=_num(hass, sources[SRC_SNOW]),
        uv=_num(hass, sources[SRC_UV]),
        wind=_num(hass, sources[SRC_WIND]),
        gust=_num(hass, sources[SRC_GUST]),
        cloud=_num(hass, sources[SRC_CLOUD]),
        condition=_text(hass, sources[SRC_CONDITION]),
        aqi=_text(hass, sources[SRC_AQI]),
    )

    forecast_entity = sources.get(SRC_FORECAST)
    if forecast_entity:
        try:
            resp = await hass.services.async_call(
                "weather", "get_forecasts",
                {"entity_id": forecast_entity, "type": "daily"},
                blocking=True, return_response=True,
            )
            forecast = (resp or {}).get(forecast_entity, {}).get("forecast", [])
            idx = 1 if day == "tomorrow" else 0
            if len(forecast) > idx:
                entry = forecast[idx]
                w.temp_max = entry.get("temperature")
                w.temp_min = entry.get("templow")
                w.rain_prob = entry.get("precipitation_probability")
                if w.rain_prob is None:
                    # Some sources (e.g. met.no) omit probability — derive a
                    # coarse one from the forecast precipitation amount (mm).
                    precip = entry.get("precipitation")
                    if precip is not None:
                        w.rain_prob = 90.0 if precip >= 2.0 else 60.0 if precip >= 0.5 else 0.0
        except Exception as err:  # forecast is best-effort
            _LOGGER.debug("Spacerek: forecast fetch failed: %s", err)

    return w


class SpacerekCoordinator(DataUpdateCoordinator):
    """Refreshes the current-conditions weather snapshot on an interval."""

    def __init__(self, hass: HomeAssistant, sources: dict) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.sources = sources

    @callback
    def async_setup_listeners(self) -> None:
        """Recompute whenever any source entity changes state.

        This makes the integration event-driven rather than purely polled: it
        fixes the cold-boot case (weather sensors are still `unavailable` when
        we first refresh, then populate a moment later) and keeps the
        recommendations fresh on every weather update. The 15-minute interval
        from __init__ stays on as a backstop.
        """
        entity_ids = sorted({e for e in self.sources.values() if e})
        async_track_state_change_event(self.hass, entity_ids, self._source_changed)

    @callback
    def _source_changed(self, event) -> None:
        self.hass.async_create_task(self.async_request_refresh())

    async def _async_update_data(self) -> Weather:
        return await async_build_weather(self.hass, self.sources, "today")
