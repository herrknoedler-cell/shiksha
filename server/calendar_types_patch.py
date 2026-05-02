"""
SHIKSHA · Calendar — Erweiterte Event-Typen (Patch)

In /opt/shiksha/kita_compliance_router.py die bestehenden Dictionaries
EVENT_TYPE_COLORS und EVENT_TYPE_LABELS ERSETZEN durch die untenstehenden
Versionen. Alternativ per Server-Befehl unten patchen.

Neue Typen:
  - vacation       — Urlaub (z.B. Mitarbeiter-Urlaub)
  - absence        — Abwesenheit / Krankheit / Termin
  - course         — Kurs / Workshop für Kinder
"""

EVENT_TYPE_COLORS = {
    "meeting":         "#a855f7",   # Lila — Meetings
    "birthday":        "#ffd93d",   # Gelb — Geburtstage 🎂
    "closing":         "#a0391f",   # Alert-Rot — KITA geschlossen
    "event":           "#ff8c42",   # Orange — Veranstaltungen (Sommerfest, Wandertag)
    "training":        "#00d4d4",   # Türkis — Fortbildungen
    "celebration":     "#ff4d8d",   # Pink — Feiern
    "parent_meeting":  "#6dd47e",   # Grün — Elterngespräche
    "vacation":        "#5ec5ff",   # Hellblau — Urlaub
    "absence":         "#b8a8c4",   # Grau-Lila — Abwesenheit/Krank
    "course":          "#ffb347",   # Hell-Orange — Kurse für Kinder
    "other":           "#9a8e9e",   # Grau — sonstiges
}

EVENT_TYPE_LABELS = {
    "meeting":         "Meeting",
    "birthday":        "Geburtstag 🎂",
    "closing":         "KITA geschlossen",
    "event":           "Veranstaltung",
    "training":        "Fortbildung",
    "celebration":     "Feier",
    "parent_meeting":  "Elterngespräch",
    "vacation":        "Urlaub",
    "absence":         "Abwesenheit",
    "course":          "Kurs",
    "other":           "Sonstiges",
}
