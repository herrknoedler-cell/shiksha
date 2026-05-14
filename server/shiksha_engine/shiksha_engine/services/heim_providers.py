"""Heim-Daten-Provider — interne Funktionen, die Karten-Daten liefern.

Statt jeden data_endpoint als HTTP-Roundtrip aufzurufen (was unnötig wäre,
weil's denselben Server trifft), registrieren wir die Provider-Funktionen
zentral. Eine Karte mit data_endpoint='/api/v1/heim/providers/anwesenheit_today'
wird durch direkten Funktionsaufruf bedient.

Provider-Funktionen bekommen (operator, db) und liefern ein Dict, das im
`subtitle_template` per `{schlüssel}` interpoliert wird. Plus optional
`visible` für Visibility-Rules.

Wenn ein Provider nicht existiert (Karten-YAML referenziert was, das in
Phase 1 noch nicht gebaut ist), gibt es eine Stub-Antwort zurück, sodass
die Karte gar nicht erst sichtbar wird.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from ..models import MemoryEntry, Operator, Session as ShikshaSession

log = logging.getLogger("shiksha.heim.providers")


# ===================================================================
# Provider-Registry
# ===================================================================

ProviderFunc = Callable[[Operator, DBSession], dict[str, Any]]
_REGISTRY: dict[str, ProviderFunc] = {}


def register_provider(name: str):
    """Decorator: registriert eine Provider-Funktion unter ihrem Namen."""
    def wrap(fn: ProviderFunc) -> ProviderFunc:
        if name in _REGISTRY:
            raise RuntimeError(f"Provider already registered: {name}")
        _REGISTRY[name] = fn
        return fn
    return wrap


def call_provider(
    name: str,
    operator: Operator,
    db: DBSession,
) -> dict[str, Any]:
    """Ruft einen Provider auf. Bei Fehler oder Unbekannt: visible=False.

    So fällt die Karte aus dem Heim raus, ohne dass das Frontend was merkt.
    """
    fn = _REGISTRY.get(name)
    if fn is None:
        log.warning("Heim-Provider unknown: %s", name)
        return {"visible": False}
    try:
        result = fn(operator, db)
        # Default: sichtbar, wenn Provider nichts anderes sagt
        if "visible" not in result:
            result["visible"] = True
        return result
    except Exception:
        log.exception("Heim-Provider '%s' raised", name)
        return {"visible": False}


def list_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


# ===================================================================
# Core-Provider (cross-edition)
# ===================================================================

@register_provider("memory_proposed_count")
def _memory_proposed(operator: Operator, db: DBSession) -> dict:
    """Wie viele proposed Memory-Vorschläge warten auf Bestätigung?"""
    count = db.execute(
        select(func.count(MemoryEntry.id))
        .where(MemoryEntry.operator_id == operator.id)
        .where(MemoryEntry.status == "proposed")
        .where(MemoryEntry.deleted_at.is_(None))
    ).scalar_one()
    return {
        "count":   count,
        "visible": count > 0,
    }


@register_provider("verlauf_count")
def _verlauf_count(operator: Operator, db: DBSession) -> dict:
    """Wie viele abgeschlossene Sessions hat dieser Operator?"""
    count = db.execute(
        select(func.count(ShikshaSession.id))
        .where(ShikshaSession.operator_id == operator.id)
        .where(ShikshaSession.closed_at.isnot(None))
    ).scalar_one()
    return {
        "count":   count,
        "visible": count > 0,
    }


# ===================================================================
# KITA-Stub-Provider (Phase 1 — bevor die echten Module fertig sind)
# ===================================================================

@register_provider("kita_anwesenheit_stub")
def _kita_anwesenheit_stub(operator: Operator, db: DBSession) -> dict:
    """Stub für Anwesenheit. Liefert Mock-Daten in Phase 1.

    Wird in Phase 1.5 durch echte Anwesenheits-Anbindung ersetzt.
    """
    return {
        "present_count": "—",
        "total_count":   "—",
        "visible":       True,  # Karte ist sichtbar mit Strich-Platzhaltern
    }


@register_provider("kita_kalender_stub")
def _kita_kalender_stub(operator: Operator, db: DBSession) -> dict:
    """Stub für Kalender. Liefert Mock-Daten.

    Nicht mehr in kita.yaml referenziert seit 5.5.4.6.a — die Karte 'heute'
    nutzt jetzt calendar_summary. Stub-Funktion bleibt für Rückwärts-Kompat
    falls jemand sie via API direkt aufruft.
    """
    return {
        "event_count":    0,
        "first_event_at": None,
        "visible":        True,
    }


# ===================================================================
# Calendar-Provider (5.5.4.6.a)
# ===================================================================

@register_provider("calendar_summary")
def _calendar_summary(operator: Operator, db: DBSession) -> dict:
    """Provider für Heim-Karten 'Heute', 'Diese Woche', 'Kalender'.

    Tenant wird aus operator.org_id abgeleitet (wie bei allen Providern).
    Liefert drei Counter, die im kita.yaml-Template eingesetzt werden:
      event_count_today  — Anzahl Events heute
      staff_count_today  — Staff ohne Urlaub/Abwesenheit heute
      event_count_week   — Anzahl Events im Mo-So-Fenster
    """
    from shiksha_engine.services.calendar_query import (
        compute_event_stats,
        compute_today_summary,
    )
    if not operator.org_id:
        return {"event_count_today": 0, "staff_count_today": 0, "event_count_week": 0, "visible": False}
    today = compute_today_summary(db, operator.org_id, operator)
    stats = compute_event_stats(db, operator.org_id, operator)
    return {
        "event_count_today": today["event_count_today"],
        "staff_count_today": today["staff_count_today"],
        "event_count_week":  stats["this_week"],
        "visible":           True,
    }


# ===================================================================
# Visibility-Rule-Auswerter
# ===================================================================

def evaluate_visibility(rule: str | None, data: dict) -> bool:
    """Wertet eine einfache Visibility-Regel aus.

    Unterstützt: `count > 0`, `count >= N`, `visible == True/False`,
    `not <feld>`, `<feld> > N`, `<feld> >= N`.

    Wenn rule None oder leer: True.
    Wenn data sagt `visible=False`: immer False (Provider hat entschieden).
    Bei Parse-Fehler: False (sicherer Default).
    """
    if data.get("visible") is False:
        return False
    if not rule:
        return True

    rule = rule.strip()

    # Pattern: "<feld> <op> <wert>"  oder  "not <feld>"
    try:
        if rule.startswith("not "):
            field = rule[4:].strip()
            return not data.get(field)

        # Versuche Ausdruck mit Operator zu parsen
        for op_str, fn in (
            (">=", lambda a, b: a >= b),
            ("<=", lambda a, b: a <= b),
            ("==", lambda a, b: a == b),
            ("!=", lambda a, b: a != b),
            (">",  lambda a, b: a > b),
            ("<",  lambda a, b: a < b),
        ):
            if op_str in rule:
                left, right = rule.split(op_str, 1)
                left_val = data.get(left.strip())
                if left_val is None:
                    return False
                right_str = right.strip()
                # right_str könnte True/False oder Zahl sein
                if right_str in ("True", "true"):
                    return fn(left_val, True)
                if right_str in ("False", "false"):
                    return fn(left_val, False)
                try:
                    right_val = int(right_str)
                except ValueError:
                    right_val = right_str.strip('"\'')
                return fn(left_val, right_val)

        # Fallback: nur Feldname → truthy check
        return bool(data.get(rule))
    except Exception:
        log.warning("Visibility rule could not be evaluated: %r", rule)
        return False


# ===================================================================
# Subtitle-Template-Renderer
# ===================================================================

def render_subtitle(template: str | None, data: dict) -> str | None:
    """Setzt {feld}-Platzhalter im Template mit Werten aus data ein."""
    if template is None:
        return None
    # Empty-string-Template darf nicht auf None mappen — strikte None-Check.
    try:
        return template.format(**data)
    except (KeyError, IndexError, ValueError):
        # Fehlende Felder → Original-Template zurück
        return template
