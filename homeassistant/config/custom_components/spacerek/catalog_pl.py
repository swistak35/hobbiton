"""Polish-language content for Spacerek: clothing catalogue, notes, labels.

All user-facing text lives here, separated from the decision logic in
engine.py. No Home Assistant imports — safe to use standalone.
"""

# Clothing per warmth level (0 = lightest .. 8 = warmest), keyed by catalogue.
# "baby" uses bodysuit-based vocabulary, "child" uses regular clothes.
CATALOG = {
    "baby": {
        0: ["Body z krótkim rękawem (przewiewne)"],
        1: ["Body z krótkim rękawem", "Krótkie spodenki lub cienkie legginsy"],
        2: ["Body z długim rękawem", "Krótkie spodenki lub cienkie długie spodnie"],
        3: ["Body z długim rękawem", "Długie spodnie", "Skarpetki"],
        4: ["Body z długim rękawem", "Długie spodnie", "Bluza", "Cienka czapka", "Skarpetki"],
        5: ["Body z długim rękawem", "Długie spodnie", "Polar lub gruba bluza",
            "Kurtka przejściowa", "Czapka", "Skarpetki"],
        6: ["Body z długim rękawem", "Ciepłe spodnie", "Kurtka zimowa lub kombinezon",
            "Czapka", "Rękawiczki", "Grube skarpetki"],
        7: ["Bielizna termoaktywna lub body z długim rękawem", "Kombinezon zimowy",
            "Czapka", "Komin", "Rękawiczki", "Ciepłe skarpety"],
        8: ["Warstwa termoaktywna", "Gruby kombinezon zimowy", "Czapka",
            "Komin", "Rękawiczki", "Wełniane skarpety"],
    },
    "child": {
        0: ["T-shirt (przewiewny)", "Krótkie spodenki"],
        1: ["T-shirt", "Krótkie spodenki lub cienkie spodnie"],
        2: ["Koszulka z długim rękawem", "Długie spodnie"],
        3: ["Bluza", "Długie spodnie", "Cienka kurtka"],
        4: ["Bluza", "Długie spodnie", "Kurtka przejściowa", "Cienka czapka"],
        5: ["Polar lub gruba bluza", "Długie spodnie", "Cieplejsza kurtka", "Czapka"],
        6: ["Ciepła bluza", "Ocieplane spodnie", "Kurtka zimowa", "Czapka",
            "Rękawiczki", "Komin"],
        7: ["Bielizna termoaktywna", "Ocieplane spodnie", "Gruba kurtka zimowa",
            "Czapka", "Rękawiczki", "Szalik lub komin"],
        8: ["Bielizna termoaktywna", "Spodnie ocieplane", "Gruba kurtka lub kombinezon",
            "Czapka", "Rękawiczki", "Komin", "Grube skarpety"],
    },
}

# Accessory / safety note texts, referenced by key from engine.py.
NOTES = {
    "rain_pram": "Pokrowiec lub folia przeciwdeszczowa na wózek",
    "rain_clothes": "Kurtka lub peleryna przeciwdeszczowa",
    "rain_boots": "Kalosze",
    "rain_short": "Przy intensywnym deszczu skróć czas na zewnątrz",
    "rain_maybe": "Spakuj kurtkę przeciwdeszczową – w ciągu dnia możliwy deszcz",
    "snow_gear": "Wodoodporne rękawiczki i śniegowce lub ocieplane kalosze",
    "hat_sun": "Czapka z daszkiem lub kapelusz przeciwsłoneczny",
    "spf": "Krem z filtrem SPF 30+ na odsłonięte części ciała",
    "no_spf_shade": ("Dziecko poniżej 6. miesiąca: bez kremów z filtrem – "
                     "zadbaj o cień i osłonięcie ubraniem"),
    "uv_high": "Wysokie UV – ogranicz ekspozycję między 11:00 a 15:00, wybieraj cień",
    "pram_no_cover": ("Nie przykrywaj gondoli kocykiem „dla cienia” – grozi "
                      "przegrzaniem; użyj przewiewnej osłonki"),
    "sweat_insert": "Wkładka antypotowa lub tetrowa pieluszka pod plecy",
    "muslin": "Lekki kocyk muślinowy lub bambusowy (przewiewny)",
    "water": "Zabierz wodę do picia",
    "heat_check_neck": "Sprawdzaj kark – powinien być ciepły i suchy, nie spocony",
    "heat_general": "W upale skróć spacer i wybieraj zacienione trasy",
    "heat_reconsider": "Rozważ przełożenie wyjścia na chłodniejszą porę dnia",
    "cold_check": "Sprawdzaj dłonie, nos i policzki; przy mrozie skróć wyjście",
    "cold_blanket": "Ciepły kocyk lub śpiworek do wózka",
    "cold_extreme": "Mróz – ogranicz wyjście do niezbędnego minimum",
    "wind_neck": "Komin lub szalik chroniący szyję i uszy",
    "wind_pram": "Podnieś budkę wózka od strony wiatru",
    "aqi_moderate": "Umiarkowana jakość powietrza – dla niemowlęcia rozważ krótszy spacer",
    "aqi_bad": "Zła jakość powietrza – rozważ rezygnację z wyjścia, zwłaszcza z niemowlęciem",
    "car_no_coat": ("Nie zapinaj dziecka w grubej kurtce ani kombinezonie – pasy muszą "
                    "przylegać; ciepło zapewnij kocykiem po zapięciu"),
    "car_ac": "Klimatyzacja ok. 22–23°C; nie kieruj nawiewu wprost na dziecko",
    "car_shades": "Osłonki przeciwsłoneczne na szyby",
    "car_blanket": "Kocyk na nóżki (zakładaj po zapięciu pasów)",
    "gondola_cooler": "Brak słońca w gondoli sprawia, że jest chłodniej – długi rękaw bywa optymalny",
    "gondola_blanket": "Lekki kocyk w pogotowiu",
    "gondola_net": "Przewiewna osłonka lub moskitiera na gondolę",
    "preschool_layers": "Ubierz „na cebulkę” – warstwy łatwe do samodzielnego zdejmowania",
    "preschool_spare": "Zapasowy komplet ubrań w plecaku",
    "spare_layer": "Dodatkowa warstwa (bluza/kurtka) spakowana na zapas, do zdjęcia",
    "no_data": "Brak danych z czujników pogodowych – sprawdź konfigurację źródeł",
}

# Home Assistant weather condition slug → Polish label.
CONDITION_PL = {
    "clear-night": "bezchmurnie (noc)",
    "cloudy": "pochmurno",
    "fog": "mgła",
    "hail": "grad",
    "lightning": "burza",
    "lightning-rainy": "burza z deszczem",
    "partlycloudy": "częściowe zachmurzenie",
    "pouring": "ulewa",
    "rainy": "deszcz",
    "snowy": "śnieg",
    "snowy-rainy": "deszcz ze śniegiem",
    "sunny": "słonecznie",
    "windy": "wietrznie",
    "windy-variant": "wietrznie",
    "exceptional": "ekstremalne warunki",
}

# GIOŚ air-quality index enum → Polish label.
AQI_PL = {
    "very_good": "bardzo dobra",
    "good": "dobra",
    "moderate": "umiarkowana",
    "sufficient": "dostateczna",
    "bad": "zła",
    "very_bad": "bardzo zła",
}


def condition_pl(slug):
    if not slug:
        return None
    return CONDITION_PL.get(slug, slug)


def aqi_pl(slug):
    if not slug:
        return None
    return AQI_PL.get(slug, slug)


def _years_word(n: int) -> str:
    if n == 1:
        return "rok"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return "lata"
    return "lat"


def format_age(days: int, months: int, years: int) -> str:
    """Human, Polish age string scaled to the child's age."""
    if days < 14:
        return f"{days} dni"
    if days < 60:
        return f"{days // 7} tyg."
    if months < 24:
        return f"{months} mies."
    return f"{years} {_years_word(years)}"
