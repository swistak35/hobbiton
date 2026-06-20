"""Standalone exerciser for the Spacerek engine — run with `python3 selftest.py`.

Verifies the algorithm without Home Assistant: builds the two real children
(Filip, Łucja) as of a fixed date and prints recommendations for a range of
weather scenarios, including the 25°C/feels-23°C case from the phone app.
"""
from datetime import date

try:
    from . import engine as E
except ImportError:
    import engine as E

TODAY = date(2026, 6, 18)
FILIP = E.make_child("Filip", date(2026, 4, 18), TODAY)      # ~2 months
LUCJA = E.make_child("Łucja", date(2020, 10, 7), TODAY)      # 5 years

SCENARIOS = {
    "App 25°C, pochmurno, powietrze świetne (jak na screenach)": E.Weather(
        temp=25, feels_like=23, condition="cloudy", cloud=75, uv=3,
        wind=10, gust=18, aqi="very_good", rain_rate=0,
        temp_min=16, temp_max=26, rain_prob=10),
    "Upał 32°C, słonecznie, UV 8": E.Weather(
        temp=32, feels_like=34, condition="sunny", cloud=5, uv=8,
        wind=8, gust=15, aqi="good", rain_rate=0,
        temp_min=22, temp_max=33, rain_prob=0),
    "Deszcz 12°C": E.Weather(
        temp=12, feels_like=10, condition="rainy", cloud=100, uv=1,
        wind=20, gust=35, aqi="good", rain_rate=2.0,
        temp_min=9, temp_max=14, rain_prob=80),
    "Mróz -8°C, wietrznie": E.Weather(
        temp=-8, feels_like=-14, condition="cloudy", cloud=80, uv=0,
        wind=25, gust=40, aqi="moderate", rain_rate=0, snow_rate=0.5,
        temp_min=-11, temp_max=-5, rain_prob=20),
}


def show(child, activity_key, w):
    a = E.ACTIVITIES[activity_key]
    r = E.recommend(child, a, w)
    print(f"  ── {a.label}  (poziom {r.warmth_level}, "
          f"T_eff={r.weather['temperatura_efektywna']}°C)")
    print(f"     {r.headline}")
    print(f"     UBIÓR:    {' + '.join(r.layers) or '—'}")
    if r.accessories:
        print(f"     AKCESORIA: {' | '.join(r.accessories)}")
    if r.safety:
        print(f"     UWAGI:     {' | '.join(r.safety)}")


def main():
    print(f"Filip: {FILIP.age_text}, grupa={FILIP.group}, katalog={FILIP.catalog}")
    print(f"Łucja: {LUCJA.age_text}, grupa={LUCJA.group}, katalog={LUCJA.catalog}")
    for title, w in SCENARIOS.items():
        print("\n" + "=" * 78)
        print(title)
        print("=" * 78)
        print(" FILIP (niemowlę):")
        for act in ("wozek_gondola", "samochod", "nosidlo"):
            show(FILIP, act, w)
        print(" ŁUCJA (5 lat):")
        for act in ("przedszkole", "spacer", "samochod"):
            show(LUCJA, act, w)


if __name__ == "__main__":
    main()
