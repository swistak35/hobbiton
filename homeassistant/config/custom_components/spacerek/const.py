"""Constants and tunable parameters for the Spacerek integration.

This module is intentionally free of any Home Assistant imports so that the
decision logic (engine.py + catalog_pl.py) can be imported and exercised with
plain ``python3`` — see selftest.py.
"""

DOMAIN = "spacerek"

# --- config keys ----------------------------------------------------------
CONF_SOURCES = "sources"
CONF_CHILDREN = "children"
CONF_BIRTHDATE = "birthdate"
CONF_ACTIVITIES = "activities"
CONF_CAR_CABIN = "car_cabin_temp"

# source keys (also the keys used in the YAML `sources:` block)
SRC_TEMPERATURE = "temperature"
SRC_FEELS_LIKE = "feels_like"
SRC_RAIN = "rain_rate"
SRC_SNOW = "snow_rate"
SRC_UV = "uv_index"
SRC_WIND = "wind_speed"
SRC_GUST = "wind_gust"
SRC_CLOUD = "cloud_coverage"
SRC_AQI = "air_quality"
SRC_CONDITION = "condition"
SRC_FORECAST = "forecast_entity"

# Defaults point at the entities that actually exist on this instance
# (verified live: OpenWeatherMap broken-out sensors + GIOŚ air quality).
DEFAULT_SOURCES = {
    SRC_TEMPERATURE: "sensor.openweathermap_temperature",
    SRC_FEELS_LIKE: "sensor.openweathermap_feels_like_temperature",
    SRC_RAIN: "sensor.openweathermap_rain",
    SRC_SNOW: "sensor.openweathermap_snow",
    SRC_UV: "sensor.openweathermap_uv_index",
    SRC_WIND: "sensor.openweathermap_wind_speed",
    SRC_GUST: "sensor.openweathermap_wind_gust",
    SRC_CLOUD: "sensor.openweathermap_cloud_coverage",
    SRC_AQI: "sensor.gios_wroclaw_conrada_korzeniowskiego_pm2_5_index",
    SRC_CONDITION: "weather.openweathermap",
    # OWM (not met.no) for the daily forecast: it reports rain probability and
    # is consistent with the current-conditions sensors above.
    SRC_FORECAST: "weather.openweathermap",
}

# Sensible per-age default outing types (overridable per child in config).
DEFAULT_ACTIVITIES_BABY = ["wozek_gondola", "samochod", "nosidlo"]
DEFAULT_ACTIVITIES_CHILD = ["przedszkole", "spacer", "samochod"]

# --- warmth ladder --------------------------------------------------------
# Level 0 = hottest/lightest .. MAX_LEVEL = coldest/heaviest.
# A given effective temperature T_eff maps to the first level whose lower
# bound it clears. BAND_LOWER[i] is the inclusive lower bound (°C) of level i.
MAX_LEVEL = 8
BAND_LOWER = [
    27.0,   # L0  >= 27
    23.0,   # L1  23 .. 27
    19.0,   # L2  19 .. 23
    15.0,   # L3  15 .. 19
    11.0,   # L4  11 .. 15
    7.0,    # L5   7 .. 11
    3.0,    # L6   3 .. 7
    -2.0,   # L7  -2 .. 3
]           # L8  < -2


def level_from_temp(t_eff: float) -> int:
    """Map an effective temperature to a warmth level (0..MAX_LEVEL)."""
    for level, lower in enumerate(BAND_LOWER):
        if t_eff >= lower:
            return level
    return MAX_LEVEL


# --- effective-temperature offsets (°C) -----------------------------------
DEFAULT_CAR_CABIN_TEMP = 23.0   # A/C cabin reference for the car activity
OFFSET_CLAMP = 4.0              # total environmental offset is clamped to ±this

OFF_SUN_STRONG = 2.0           # clear sky + meaningful UV, sun-exposed
OFF_SUN_PARTIAL = 1.0          # broken cloud + meaningful UV
OFF_SHADE = -1.0               # shaded route / pram canopy
OFF_GONDOLA_NOSUN = -1.0       # enclosed carrycot feels cooler (no solar gain)
OFF_ACTIVE = 1.0               # child generates heat (walking, playing)
OFF_CARRIED = 1.0              # carried / babywearing: parent's body heat
OFF_INACTIVE = -1.0            # sitting/lying still in a stroller
OFF_GUST = -1.0               # strong gusts on an exposed child

# thresholds used by the offset + rule logic
GUST_THRESHOLD = 30.0          # km/h
UV_SUN_MIN = 3.0               # UV index at which "sun" matters
UV_HIGH = 6.0                  # high-UV safety advice
CLOUD_STRONG_SUN = 40.0        # % cloud below which sun is "strong"
CLOUD_PARTIAL_SUN = 70.0       # % cloud below which sun is "partial"
RAIN_RATE_MIN = 0.1            # mm/h treated as "raining"
RAIN_POURING_RATE = 1.0        # mm/h treated as heavy rain
RAIN_PROB_PACK = 40.0          # daily rain probability (%) → pack rain gear
WARM_TEMP = 24.0               # °C (actual) → warm-weather accessories
HOT_TEMP = 28.0               # °C (actual) → hot-weather advice
HOT_TEFF = 27.0               # °C (effective) → hot-weather advice

# --- age handling (months) ------------------------------------------------
AGE_NEWBORN_MAX = 3
AGE_INFANT_MAX = 12
AGE_TODDLER_MAX = 48
AGE_PRESCHOOL_MAX = 84
CATALOG_CHILD_MIN_MONTHS = 36   # younger → "baby" vocabulary, older → "child"
SPF_MIN_MONTHS = 6              # sunscreen only recommended from 6 months

# Newborns/infants get "one more layer than an adult", but only once it is
# genuinely cool — in warm weather the dominant risk is overheating.
AGE_BUMP_FROM_LEVEL = {
    "newborn": 3,
    "infant": 4,
    "toddler": 6,
}

CAR_SEAT_MAX_LEVEL = 3          # never bundle a child bulkily under the harness

# --- air-quality severity (GIOŚ index enum) -------------------------------
AQI_SEVERITY = {
    "very_good": 0,
    "good": 1,
    "moderate": 2,
    "sufficient": 3,
    "bad": 4,
    "very_bad": 5,
}

RAINY_CONDITIONS = {"rainy", "pouring", "lightning-rainy", "snowy-rainy"}
SNOWY_CONDITIONS = {"snowy", "snowy-rainy", "hail"}
