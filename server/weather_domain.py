# ============================================================
# SHIKSHA — weather_domain.py
# Echter Domain-Call: Open-Meteo API
# Kein API-Key nötig. Kostenlos. DSGVO-konform (Server in Europa).
# Dokumentation: https://open-meteo.com/en/docs
# ============================================================

from __future__ import annotations
import httpx
from datetime import date, datetime, timezone
from models import DomainResult


# ------------------------------------------------------------
# OPEN-METEO WMO WEATHER CODES
# Übersetzung der numerischen Wettercodes in lesbare Zustände
# ------------------------------------------------------------

WMO_CODES: dict[int, str] = {
    0:  "clear_sky",
    1:  "mainly_clear", 2: "partly_cloudy", 3: "overcast",
    45: "fog", 48: "icy_fog",
    51: "drizzle_light", 53: "drizzle_moderate", 55: "drizzle_heavy",
    61: "rain_light", 63: "rain_moderate", 65: "rain_heavy",
    71: "snow_light", 73: "snow_moderate", 75: "snow_heavy",
    77: "snow_grains",
    80: "showers_light", 81: "showers_moderate", 82: "showers_heavy",
    85: "snow_showers_light", 86: "snow_showers_heavy",
    95: "thunderstorm", 96: "thunderstorm_hail", 99: "thunderstorm_heavy_hail",
}

# Outdoor-Tauglichkeit aus Wetterbedingung ableiten
OUTDOOR_SUITABILITY: dict[str, str] = {
    "clear_sky": "good", "mainly_clear": "good", "partly_cloudy": "good",
    "overcast": "conditional",
    "fog": "conditional", "icy_fog": "not_suitable",
    "drizzle_light": "conditional", "drizzle_moderate": "conditional",
    "drizzle_heavy": "not_suitable",
    "rain_light": "conditional", "rain_moderate": "not_suitable",
    "rain_heavy": "not_suitable",
    "snow_light": "conditional", "snow_moderate": "not_suitable",
    "snow_heavy": "not_suitable", "snow_grains": "not_suitable",
    "showers_light": "conditional", "showers_moderate": "not_suitable",
    "showers_heavy": "not_suitable",
    "snow_showers_light": "not_suitable", "snow_showers_heavy": "not_suitable",
    "thunderstorm": "not_suitable", "thunderstorm_hail": "not_suitable",
    "thunderstorm_heavy_hail": "not_suitable",
}

# Sailing-Tauglichkeit aus Windgeschwindigkeit
def sailing_suitability(wind_kmh: float, gusts_kmh: float) -> str:
    if gusts_kmh > 60 or wind_kmh > 50:
        return "not_suitable"       # Sturmwarnung
    if gusts_kmh > 40 or wind_kmh > 30:
        return "conditional"        # erhöhtes Risiko
    return "suitable"


# ------------------------------------------------------------
# HAUPT-FUNKTION
# ------------------------------------------------------------

async def call_weather_domain_real(
    location_id: str,
    latitude: float,
    longitude: float,
    target_date: date,
    location_name: str = "",
    is_sailing: bool = False,
) -> DomainResult:
    """
    Echter Wetter-Domain-Call via Open-Meteo.

    Parameter:
        location_id:   Entity-ID des Standorts (z.B. "loc_lake_02")
        latitude:      Breitengrad
        longitude:     Längengrad
        target_date:   Datum für das die Prüfung gilt
        location_name: Lesbare Bezeichnung für Query-String
        is_sailing:    True = sailing_suitability zusätzlich prüfen

    Gibt zurück: DomainResult mit echten Wetterdaten
    """

    date_str = target_date.isoformat()
    query = f"Wetterbedingungen {location_name or location_id} am {date_str}"

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":             latitude,
        "longitude":            longitude,
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
        ]),
        "wind_speed_unit":      "kmh",
        "timezone":             "Europe/Vienna",
        "start_date":           date_str,
        "end_date":             date_str,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

    except httpx.TimeoutException:
        return _fallback_result(query, location_id, "timeout")
    except httpx.HTTPStatusError as e:
        return _fallback_result(query, location_id, f"http_{e.response.status_code}")
    except Exception as e:
        return _fallback_result(query, location_id, str(e))

    # ------------------------------------------------------------
    # Daten auslesen
    # ------------------------------------------------------------
    daily = data.get("daily", {})

    wmo_code        = daily.get("weather_code",               [None])[0]
    temp_max        = daily.get("temperature_2m_max",         [None])[0]
    temp_min        = daily.get("temperature_2m_min",         [None])[0]
    precip          = daily.get("precipitation_sum",          [None])[0]
    precip_prob     = daily.get("precipitation_probability_max", [None])[0]
    wind_max        = daily.get("wind_speed_10m_max",         [None])[0]
    gusts_max       = daily.get("wind_gusts_10m_max",         [None])[0]

    condition = WMO_CODES.get(wmo_code, "unknown") if wmo_code is not None else "unknown"
    outdoor   = OUTDOOR_SUITABILITY.get(condition, "conditional")

    # Regen-Wahrscheinlichkeit normalisieren (0–1)
    rain_prob_normalized = round((precip_prob or 0) / 100, 2)

    # Sturmwarnung: Windböen > 60 km/h
    storm_warning = bool(gusts_max and gusts_max > 60)

    result: dict = {
        "condition":                condition,
        "wmo_code":                 wmo_code,
        "temperature_max_c":        temp_max,
        "temperature_min_c":        temp_min,
        "precipitation_mm":         precip,
        "rain_probability":         rain_prob_normalized,
        "wind_speed_kmh":           wind_max,
        "wind_gusts_kmh":           gusts_max,
        "storm_warning":            storm_warning,
        "outdoor_suitability":      outdoor,
        "forecast_confidence":      0.85,       # Open-Meteo Tagesvorhersage ~85%
        "data_freshness":           "live",
        "fetched_at":               datetime.now(timezone.utc).isoformat(),
        "uncertainty_note":         None,
    }

    # Sailing-spezifische Bewertung
    if is_sailing and wind_max is not None and gusts_max is not None:
        result["segeleignung"] = sailing_suitability(wind_max, gusts_max)
        if storm_warning:
            result["storm_window"] = "ganztags (genaue Zeiten in Stundendaten verfügbar)"

    # Decision impact: kritisch bei Sturm oder not_suitable
    if storm_warning or outdoor == "not_suitable":
        decision_impact = "critical"
    elif outdoor == "conditional":
        decision_impact = "high"
    else:
        decision_impact = "medium"

    return DomainResult(
        domain="weather",
        query=query,
        result=result,
        decision_impact=decision_impact,
        checkpoint_passed=True,
    )


# ------------------------------------------------------------
# FALLBACK — wenn API nicht erreichbar
# ------------------------------------------------------------

def _fallback_result(query: str, location_id: str, error: str) -> DomainResult:
    """
    Gibt einen sicheren Fallback zurück wenn die API nicht erreichbar ist.
    SHIKSHA bleibt stabil — aber markiert die Unsicherheit explizit.
    """
    return DomainResult(
        domain="weather",
        query=query,
        result={
            "condition":            "unknown",
            "outdoor_suitability":  "conditional",  # konservativ: nicht "good"
            "storm_warning":        False,
            "forecast_confidence":  0.0,
            "data_freshness":       "unavailable",
            "uncertainty_note":     f"Wetter-API nicht erreichbar ({error}). Manuelle Prüfung empfohlen.",
        },
        decision_impact="high",     # bei Unsicherheit: hohe Auswirkung
        checkpoint_passed=False,    # explizit: Checkpoint nicht bestanden
    )


# ------------------------------------------------------------
# LOCATION REGISTRY
# Bekannte Standorte mit Koordinaten
# Später: aus Location-Entity laden
# ------------------------------------------------------------

KNOWN_LOCATIONS: dict[str, dict] = {
    "loc_lake_02": {
        "name":      "Seezentrum Wolfgangsee",
        "latitude":  47.7394,
        "longitude": 13.4457,
        "is_sailing": True,
    },
    "loc_stitch_workshop_01": {
        "name":      "Stickwerkstatt Wien",
        "latitude":  48.2082,
        "longitude": 16.3738,
        "is_sailing": False,
    },
}


async def get_weather_for_location(
    location_id: str,
    target_date: date,
) -> DomainResult:
    """
    Vereinfachter Aufruf über location_id.
    Koordinaten kommen aus KNOWN_LOCATIONS — später aus Entity Memory.
    """
    loc = KNOWN_LOCATIONS.get(location_id)
    if not loc:
        return _fallback_result(
            query=f"Wetterbedingungen {location_id} am {target_date}",
            location_id=location_id,
            error=f"location_id '{location_id}' nicht in Registry",
        )

    return await call_weather_domain_real(
        location_id=location_id,
        latitude=loc["latitude"],
        longitude=loc["longitude"],
        target_date=target_date,
        location_name=loc["name"],
        is_sailing=loc.get("is_sailing", False),
    )
