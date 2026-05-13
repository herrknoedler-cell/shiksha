"""Event-Type-Validation und Edition-spezifische Helpers.

Konventionen aus SHIKSHA_CALENDAR_SPEC.md §3.
"""
from __future__ import annotations

from shiksha_engine.models.event import (
    EVENT_TYPES_BY_EDITION,
    URGENCY_LEVELS,
    URLAUB_STATUS,
    VIRTUAL_EVENT_TYPES,
)


def is_valid_type(edition: str, event_type: str) -> bool:
    """Prüft, ob event_type für die gegebene Edition zulässig ist.

    Virtuelle Typen (geburtstag) sind NIE in Create-Payloads zulässig —
    sie werden nur vom Backend gemerged.
    """
    if event_type in VIRTUAL_EVENT_TYPES:
        return False
    allowed = EVENT_TYPES_BY_EDITION.get(edition, ())
    return event_type in allowed


def is_valid_urgency(urgency: str) -> bool:
    return urgency in URGENCY_LEVELS


def is_valid_urlaub_status(status: str) -> bool:
    return status in URLAUB_STATUS


def normalize_metadata(metadata: dict | None) -> dict:
    """Setzt Defaults für reservierte Keys; idempotent."""
    md = dict(metadata or {})
    md.setdefault("urgency", "normal")
    # status nur relevant bei event_type=urlaub — Default ist 'approved'
    md.setdefault("status", "approved")
    return md


def color_token_for(event_type: str) -> str:
    """CSS-Token-Name für event_type (wird vom Frontend für data-event-type genutzt).

    Backend braucht das nur für TodaySummary / Notifications. UI rendert
    primär via [data-event-type] CSS-Attribute-Selektoren.
    """
    mapping = {
        "termin": "var(--shk-edition-primary)",
        "urlaub": "var(--shk-edition-warm)",
        "abwesenheit": "var(--shk-color-text-faint)",
        "kurs": "var(--shk-edition-accent)",
        "geburtstag": "var(--shk-edition-warm)",
    }
    return mapping.get(event_type, "var(--shk-color-text)")
