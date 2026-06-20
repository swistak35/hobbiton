"""Spacerek decision engine — pure, deterministic, no LLM, no Home Assistant.

The whole recommendation is computed by a physical model:

  1. effective_temp(): the temperature the child's body actually experiences,
     derived from feels-like / dry-bulb + additive offsets for sun, shade,
     activity, being carried, gusts, and the enclosed pram microclimate.
  2. level_from_temp(): map that to a warmth level (a rung on a clothing ladder).
  3. apply_age(): shift the level for the child's thermoregulation (the
     paediatric "one more layer for a baby" rule, with a heat guard) and the
     car-seat safety cap.
  4. pick_outfit(): read the layers off the age-appropriate catalogue.
  5. build_notes(): a rule engine that emits accessory + safety advice from
     (weather × activity × age) predicates.

Everything is a pure function of its inputs, so selftest.py can exercise it
with plain python3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

try:  # package import (inside Home Assistant)
    from . import const as C
    from . import catalog_pl as cat
except ImportError:  # standalone import (selftest / python3)
    import const as C
    import catalog_pl as cat


# --------------------------------------------------------------------------- #
#  Data models
# --------------------------------------------------------------------------- #
@dataclass
class Weather:
    temp: Optional[float] = None          # dry-bulb air temperature, °C
    feels_like: Optional[float] = None    # apparent temperature, °C
    rain_rate: Optional[float] = None     # mm/h
    snow_rate: Optional[float] = None     # mm/h
    condition: Optional[str] = None       # HA condition slug
    uv: Optional[float] = None            # UV index
    wind: Optional[float] = None          # km/h
    gust: Optional[float] = None          # km/h
    cloud: Optional[float] = None         # %
    aqi: Optional[str] = None             # GIOŚ index enum
    temp_min: Optional[float] = None      # daily forecast low, °C
    temp_max: Optional[float] = None      # daily forecast high, °C
    rain_prob: Optional[float] = None     # daily rain probability, %


@dataclass(frozen=True)
class Activity:
    key: str
    label: str
    phrase: str                  # accusative phrase for the headline
    enclosed: bool = False       # carrycot / gondola: wind-protected microclimate
    climate_controlled: bool = False   # car: cabin A/C, weather irrelevant
    sun_exposed: bool = False
    shaded: bool = False
    child_active: bool = False   # generates body heat
    inactive: bool = False       # sitting/lying still
    carried: bool = False        # babywearing: parent's body heat
    full_day: bool = False       # use the daily forecast range
    pram: bool = False           # uses a stroller/pram (rain cover etc.)


ACTIVITIES = {
    "spacer": Activity(
        "spacer", "Spacer", "na spacer", sun_exposed=True, child_active=True),
    "nosidlo": Activity(
        "nosidlo", "Nosidło lub chusta", "na spacer", sun_exposed=True, carried=True),
    "wozek_spacerowka": Activity(
        "wozek_spacerowka", "Wózek spacerowy", "na spacer",
        sun_exposed=True, inactive=True, pram=True),
    "wozek_gondola": Activity(
        "wozek_gondola", "Wózek (gondola)", "na spacer",
        enclosed=True, shaded=True, inactive=True, pram=True),
    "samochod": Activity(
        "samochod", "Samochód", "na przejażdżkę", climate_controlled=True),
    "przedszkole": Activity(
        "przedszkole", "Przedszkole (cały dzień)", "do przedszkola",
        sun_exposed=True, child_active=True, full_day=True),
}


@dataclass
class ChildInfo:
    name: str
    age_months: int
    age_days: int
    age_text: str
    group: str        # newborn / infant / toddler / preschool / child
    catalog: str      # baby / child


@dataclass
class Recommendation:
    child: dict
    activity: dict
    weather: dict
    headline: str
    warmth_level: int
    layers: list = field(default_factory=list)
    accessories: list = field(default_factory=list)
    safety: list = field(default_factory=list)

    @property
    def summary(self) -> str:
        return " + ".join(self.layers) if self.layers else self.headline

    def to_dict(self) -> dict:
        return {
            "child": self.child,
            "activity": self.activity,
            "weather": self.weather,
            "headline": self.headline,
            "summary": self.summary,
            "warmth_level": self.warmth_level,
            "layers": self.layers,
            "accessories": self.accessories,
            "safety": self.safety,
        }


# --------------------------------------------------------------------------- #
#  Child / age
# --------------------------------------------------------------------------- #
def make_child(name: str, birthdate: date, today: date) -> ChildInfo:
    """Compute age + grouping for a child as of ``today`` (pure)."""
    days = (today - birthdate).days
    months = (today.year - birthdate.year) * 12 + (today.month - birthdate.month)
    if today.day < birthdate.day:
        months -= 1
    months = max(months, 0)
    days = max(days, 0)
    years = months // 12

    if months < C.AGE_NEWBORN_MAX:
        group = "newborn"
    elif months < C.AGE_INFANT_MAX:
        group = "infant"
    elif months < C.AGE_TODDLER_MAX:
        group = "toddler"
    elif months < C.AGE_PRESCHOOL_MAX:
        group = "preschool"
    else:
        group = "child"

    catalog = "child" if months >= C.CATALOG_CHILD_MIN_MONTHS else "baby"
    return ChildInfo(
        name=name,
        age_months=months,
        age_days=days,
        age_text=cat.format_age(days, months, years),
        group=group,
        catalog=catalog,
    )


def _aqi_severity(aqi: Optional[str]) -> int:
    return C.AQI_SEVERITY.get(aqi, 0) if aqi else 0


# --------------------------------------------------------------------------- #
#  Effective temperature
# --------------------------------------------------------------------------- #
def effective_temp(w: Weather, a: Activity, car_cabin: float) -> Optional[float]:
    """Temperature the child's body experiences for this activity, or None."""
    if a.climate_controlled:
        return car_cabin

    if a.enclosed:
        base = w.temp if w.temp is not None else w.feels_like
    elif a.full_day:
        base = w.temp_min
        if base is None:
            base = w.feels_like if w.feels_like is not None else w.temp
    else:
        base = w.feels_like if w.feels_like is not None else w.temp

    if base is None:
        return None

    off = 0.0
    if a.sun_exposed and not a.shaded:
        cloud = w.cloud if w.cloud is not None else 100.0
        uv = w.uv or 0.0
        if uv >= C.UV_SUN_MIN and cloud < C.CLOUD_STRONG_SUN:
            off += C.OFF_SUN_STRONG
        elif uv >= C.UV_SUN_MIN and cloud < C.CLOUD_PARTIAL_SUN:
            off += C.OFF_SUN_PARTIAL
    if a.shaded:
        off += C.OFF_SHADE
    if a.enclosed:
        off += C.OFF_GONDOLA_NOSUN
    if a.child_active:
        off += C.OFF_ACTIVE
    if a.carried:
        off += C.OFF_CARRIED
    if a.inactive:
        off += C.OFF_INACTIVE
    if (a.sun_exposed and not a.enclosed
            and (w.gust or 0.0) >= C.GUST_THRESHOLD):
        off += C.OFF_GUST

    off = max(-C.OFFSET_CLAMP, min(C.OFFSET_CLAMP, off))
    return base + off


# --------------------------------------------------------------------------- #
#  Age modifier
# --------------------------------------------------------------------------- #
def apply_age(level: int, child: ChildInfo, a: Activity) -> tuple[int, bool]:
    """Shift the warmth level for age/thermoregulation. Returns (level, spare).

    ``spare`` flags that an active older child should carry a removable layer.
    """
    if a.climate_controlled:
        # Cabin is controlled; never bundle bulkily under a car-seat harness.
        return min(level, C.CAR_SEAT_MAX_LEVEL), False

    spare = False
    bump_from = C.AGE_BUMP_FROM_LEVEL.get(child.group)
    if bump_from is not None:
        if level >= bump_from:
            level += 1
    elif child.group == "preschool":
        if a.child_active and level >= 1:
            level -= 1
            spare = True

    return max(0, min(C.MAX_LEVEL, level)), spare


def pick_outfit(level: int, catalog: str) -> list:
    return list(cat.CATALOG[catalog][level])


# --------------------------------------------------------------------------- #
#  Accessory + safety rule engine
# --------------------------------------------------------------------------- #
def build_notes(w, a, child, level, spare, t_eff):
    acc: list = []
    saf: list = []

    def add(lst, key):
        text = cat.NOTES[key]
        if text not in lst:
            lst.append(text)

    is_infant = child.group in ("newborn", "infant")
    under6 = child.age_months < C.SPF_MIN_MONTHS
    sev = _aqi_severity(w.aqi)

    raining = (w.rain_rate or 0.0) >= C.RAIN_RATE_MIN or w.condition in C.RAINY_CONDITIONS
    pouring = (w.rain_rate or 0.0) >= C.RAIN_POURING_RATE or w.condition == "pouring"
    snowing = (w.snow_rate or 0.0) > 0.0 or w.condition in C.SNOWY_CONDITIONS
    warm = (w.temp if w.temp is not None else -99) >= C.WARM_TEMP
    hot = ((w.temp if w.temp is not None else -99) >= C.HOT_TEMP
           or (t_eff if t_eff is not None else -99) >= C.HOT_TEFF)
    cold = level >= 6
    very_cold = level >= 8
    sunny = (a.sun_exposed and not a.shaded
             and (w.cloud is None or w.cloud < C.CLOUD_PARTIAL_SUN)
             and (w.uv or 0.0) >= C.UV_SUN_MIN)

    # --- rain / snow ---
    if raining:
        if a.pram:
            add(acc, "rain_pram")
        else:
            add(acc, "rain_clothes")
            if child.catalog == "child":
                add(acc, "rain_boots")
        if pouring:
            add(saf, "rain_short")
    elif a.full_day and (w.rain_prob or 0.0) >= C.RAIN_PROB_PACK:
        add(acc, "rain_maybe")
        if child.catalog == "child":
            add(acc, "rain_boots")
    if snowing and not a.climate_controlled:
        add(acc, "snow_gear")

    # --- sun / UV ---
    if sunny and not a.climate_controlled:
        add(acc, "hat_sun")
        if under6:
            add(saf, "no_spf_shade")
        else:
            add(acc, "spf")
        if (w.uv or 0.0) >= C.UV_HIGH:
            add(saf, "uv_high")
    if a.enclosed and (w.uv or 0.0) >= C.UV_SUN_MIN:
        add(saf, "pram_no_cover")

    # --- warm / hot ---
    if warm and not a.climate_controlled:
        if a.pram or is_infant:
            add(acc, "sweat_insert")
        add(acc, "muslin")
        if child.catalog == "baby":
            add(saf, "heat_check_neck")
    if hot and not a.climate_controlled:
        if child.catalog == "child":
            add(acc, "water")
        add(saf, "heat_general")
        if is_infant and (sev >= 2 or (w.uv or 0.0) >= C.UV_HIGH):
            add(saf, "heat_reconsider")

    # --- cold ---
    if cold and not a.climate_controlled:
        add(saf, "cold_check")
        if a.pram:
            add(acc, "cold_blanket")
    if very_cold and not a.climate_controlled:
        add(saf, "cold_extreme")

    # --- wind ---
    if a.sun_exposed and not a.enclosed and not a.climate_controlled \
            and (w.gust or 0.0) >= C.GUST_THRESHOLD:
        add(acc, "wind_neck")
        if a.pram:
            add(saf, "wind_pram")

    # --- air quality ---
    if sev >= 4:
        add(saf, "aqi_bad")
    elif sev >= 2 and is_infant:
        add(saf, "aqi_moderate")

    # --- activity-specific ---
    if a.climate_controlled:
        add(saf, "car_no_coat")
        add(saf, "car_ac")
        add(acc, "car_shades")
        add(acc, "car_blanket")
        add(saf, "heat_check_neck")
        if warm:
            add(acc, "sweat_insert")
            add(acc, "muslin")
    if a.enclosed:
        add(saf, "gondola_cooler")
        add(acc, "gondola_blanket")
        if warm or sunny:
            add(acc, "gondola_net")
    if a.full_day:
        add(saf, "preschool_layers")
        add(acc, "preschool_spare")
        if w.temp_min is not None and w.temp_max is not None:
            saf.insert(0, f"Dziś od {round(w.temp_min)}° rano do "
                          f"{round(w.temp_max)}° po południu – warstwy pozwolą się dostosować")

    if spare:
        add(acc, "spare_layer")

    return acc, saf


# --------------------------------------------------------------------------- #
#  Headline + assembly
# --------------------------------------------------------------------------- #
def _headline(child, a, w):
    if _aqi_severity(w.aqi) >= 4:
        return f"{child.name}: dziś uważaj na jakość powietrza – sprawdź uwagi poniżej."
    return f"{child.name} w tym zestawie może śmiało ruszać {a.phrase}!"


def _weather_dict(w, a, t_eff):
    out = {
        "temperatura": w.temp,
        "odczuwalna": w.feels_like,
        "temperatura_efektywna": round(t_eff, 1) if t_eff is not None else None,
        "warunki": cat.condition_pl(w.condition),
        "uv": w.uv,
        "jakosc_powietrza": cat.aqi_pl(w.aqi),
    }
    if a.full_day:
        out["min_dzienna"] = w.temp_min
        out["max_dzienna"] = w.temp_max
        out["szansa_opadow"] = w.rain_prob
    return out


def recommend(child: ChildInfo, activity: Activity, weather: Weather,
              car_cabin: float = C.DEFAULT_CAR_CABIN_TEMP) -> Recommendation:
    """Full recommendation for one child + one activity + a weather snapshot."""
    child_d = {"imie": child.name, "wiek": child.age_text, "grupa": child.group}
    activity_d = {"klucz": activity.key, "nazwa": activity.label}

    t_eff = effective_temp(weather, activity, car_cabin)
    if t_eff is None:
        return Recommendation(
            child=child_d, activity=activity_d,
            weather=_weather_dict(weather, activity, None),
            headline=cat.NOTES["no_data"], warmth_level=-1,
            layers=[], accessories=[], safety=[cat.NOTES["no_data"]])

    base = C.level_from_temp(t_eff)
    level, spare = apply_age(base, child, activity)
    layers = pick_outfit(level, child.catalog)
    acc, saf = build_notes(weather, activity, child, level, spare, t_eff)

    return Recommendation(
        child=child_d, activity=activity_d,
        weather=_weather_dict(weather, activity, t_eff),
        headline=_headline(child, activity, weather),
        warmth_level=level, layers=layers, accessories=acc, safety=saf)
