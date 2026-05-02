"""
SHIKSHA · SCHULE.EDITION · Orchestrator V1
Stand: 25.04.2026

Architektur (V4):
- Sprache entsteht im Orchestrator, nie im DomainBrain (Prinzip 3)
- text_key + params, nie direkter String (Prinzip 4)
- review_required = True per Default (Prinzip 11)
- Confidence in Sprache, nicht Prozent (Prinzip 14)
- conservative = Standardmodus bei Konflikt (Prinzip 7)

Verantwortung:
1. Signale aus DB sammeln und gewichten
2. Patterns erkennen (Wiederholungen, Cluster)
3. SchoolState zusammensetzen mit natürlich-sprachlicher Summary
4. Recommended Focus als Action-Vorschläge ausgeben (review_required)
5. Policy Gates prüfen (1-4) und in Sprache überführen
"""

from datetime import datetime, timedelta
from typing import Optional

from schule_models import (
    Action,
    LanguageOutput,
    OrchestrateRequest,
    OrchestrateResponse,
    Pattern,
    SchoolState,
    SchuleSignal,
)


# ---------------------------------------------------------------------------
# 1. Sprach-Vokabular (text_keys)
# ---------------------------------------------------------------------------

LANGUAGE_TEMPLATES: dict[str, dict[str, str]] = {
    # signal_key → mode → template (mit {placeholders})
    "schule.weather.threshold_breach": {
        "alert": "{wind} kn — über Grenze",
        "action": "Verschiebung vorschlagen?",
        "flow":   "Wind übersteigt Grenze",
    },
    "schule.weather.go_no_go_decision_due": {
        "alert": "{session} entscheiden — heute",
        "action": "Plan B vorbereiten?",
        "flow":   "{session} noch offen",
    },
    "schule.weather.communication_pending": {
        "alert": "{count} Schüler warten",
        "action": "Verschiebung kommunizieren?",
        "flow":   "Nachricht ausstehend",
    },
    "schule.consent_partial": {
        "alert": "{student} darf nicht fotografiert werden",
        "action": "{guardian} um Einverständnis bitten?",
        "flow":   "{student} fehlt Foto-Konsent",
    },
    "schule.instructor.license_expiring": {
        "alert": "{instructor} — Lizenz läuft heute",
        "action": "{instructor} an Erneuerung erinnern?",
        "flow":   "{instructor}s Lizenz endet",
    },
    "schule.instructor.overload_detected": {
        "alert": "—",
        "action": "{partner} bitten einzuspringen?",
        "flow":   "{instructor} trägt diese Woche viel",
    },
    "schule.participation.streak_broken": {
        "alert": "—",
        "action": "Bei {student} kurz nachfragen?",
        "flow":   "{student} seit {days} Tagen weg",
    },
    "schule.package.expired_unrenewed": {
        "alert": "{student} Karte überfällig",
        "action": "{student} freundlich erinnern?",
        "flow":   "{student} Karte ist aus",
    },
    "schule.package.expiring_soon": {
        "alert": "—",
        "action": "{student} an Verlängerung erinnern?",
        "flow":   "{student} Karte läuft aus",
    },
    "schule.enrollment.trial_followup_due": {
        "alert": "—",
        "action": "Bei {student} nach Probestunde fragen?",
        "flow":   "{student} hat probiert, wartet",
    },
    "schule.retention.at_risk": {
        "alert": "—",
        "action": "{student} mit Aktion abholen?",
        "flow":   "{student} könnte uns verlieren",
    },
    "schule.course.threshold_close": {
        "alert": "—",
        "action": "Letzten Platz für {course} aktiv bewerben?",
        "flow":   "{course} braucht noch {needed}",
    },
    "schule.course.understaffed": {
        "alert": "{course} morgen ohne Lehrer",
        "action": "{candidate1} oder {candidate2} fragen?",
        "flow":   "{course} braucht Lehrer",
    },
    "schule.partnership.payment_overdue": {
        "alert": "{partner} Mahnung offen",
        "action": "Zahlung jetzt anweisen?",
        "flow":   "{partner} wartet auf Zahlung",
    },
    "schule.equipment.damaged_unrepaired": {
        "alert": "—",
        "action": "{item} reparieren lassen?",
        "flow":   "{item} liegt seit {days} Tagen",
    },
}


def render_language(
    signal: SchuleSignal,
    mode: str = "flow",
) -> LanguageOutput:
    """Rendert eine LanguageOutput für ein Signal — text_key + params, kein String."""
    return LanguageOutput(
        mode=mode,  # type: ignore
        text_key=signal.signal_key,
        params=signal.params,
        priority="high" if signal.severity == "high" else "medium" if signal.severity == "mid" else "low",
    )


# ---------------------------------------------------------------------------
# 2. Pattern-Erkennung
# ---------------------------------------------------------------------------

def detect_patterns(signals: list[SchuleSignal]) -> list[Pattern]:
    """
    Einfache Pattern-Erkennung in V1:
    - Cluster gleicher signal_keys → "wiederkehrendes Muster"
    - Confidence steigt mit Häufigkeit, gedeckelt bei 0.95
    """
    by_key: dict[str, list[SchuleSignal]] = {}
    for s in signals:
        by_key.setdefault(s.signal_key, []).append(s)

    patterns: list[Pattern] = []
    for key, group in by_key.items():
        if len(group) >= 2:
            confidence = min(0.5 + 0.15 * len(group), 0.95)
            patterns.append(Pattern(
                pattern_key=f"pattern.{key}.recurring",
                description=f"{len(group)}x gesehen",
                confidence=confidence,
                related_signals=[str(s.id) for s in group if s.id],
                seen_count=len(group),
                first_seen=min((s.created_at for s in group), default=None),
                last_seen=max((s.created_at for s in group), default=None),
            ))
    return patterns


# ---------------------------------------------------------------------------
# 3. Recommended Focus
# ---------------------------------------------------------------------------

def recommend_focus(signals: list[SchuleSignal], top_k: int = 3) -> list[Action]:
    """
    Priorisiert offene Signale und schlägt Aktionen vor.
    Reihenfolge: severity (high>mid>low>info) → Alter (älter > neuer)
    """
    severity_score = {"high": 3, "mid": 2, "low": 1, "info": 0}
    open_signals = [s for s in signals if s.status == "open"]
    open_signals.sort(
        key=lambda s: (
            severity_score.get(s.severity, 0),
            -((datetime.now() - s.created_at).total_seconds() if s.created_at else 0),
        ),
        reverse=True,
    )

    actions: list[Action] = []
    for sig in open_signals[:top_k]:
        templates = LANGUAGE_TEMPLATES.get(sig.signal_key, {})
        action_text = templates.get("action", "Aktion prüfen?")
        # Render text mit params (best-effort — falls Param fehlt, bleibt {placeholder})
        try:
            rendered = action_text.format(**sig.params)
        except (KeyError, IndexError):
            rendered = action_text

        actions.append(Action(
            action_key=f"act.{sig.signal_key}",
            title=rendered,
            description=None,
            affected_entities=list(sig.related_entities.values()) if sig.related_entities else [],
            review_required=True,
            language=LanguageOutput(
                mode="action",
                text_key=sig.signal_key,
                params=sig.params,
                priority="high" if sig.severity == "high" else "medium",
            ),
        ))
    return actions


# ---------------------------------------------------------------------------
# 4. Summary-Generator (Sprache!)
# ---------------------------------------------------------------------------

def build_summary(signals: list[SchuleSignal], patterns: list[Pattern]) -> str:
    """
    Erzeugt eine 1-2-Satz-Zusammenfassung in natürlicher Sprache.
    Keine Zahlenkaskaden — nur was Operator hören will.

    Beispiele:
    - "Heute alles ruhig — eine Karte läuft bei Bernd Sailer in 5 Tagen aus."
    - "Drei Sachen drücken: Wetter morgen wackelig, Toms Lizenz endet bald, Werner zahlt nicht."
    - "Alles im grünen Bereich. Nächste Aktion: Anna freundlich erinnern."
    """
    if not signals:
        return "Heute alles ruhig. Keine offenen Signale."

    high = [s for s in signals if s.severity == "high"]
    mid = [s for s in signals if s.severity == "mid"]

    if high:
        if len(high) == 1:
            sig = high[0]
            templates = LANGUAGE_TEMPLATES.get(sig.signal_key, {})
            text = templates.get("alert", sig.signal_key)
            try:
                rendered = text.format(**sig.params)
            except (KeyError, IndexError):
                rendered = text
            return f"Achtung: {rendered}."
        else:
            return f"{len(high)} Sachen drücken heute. Wir gehen sie der Reihe nach durch."

    if mid:
        if len(mid) <= 2:
            descriptions = []
            for sig in mid[:2]:
                templates = LANGUAGE_TEMPLATES.get(sig.signal_key, {})
                text = templates.get("flow", sig.signal_key)
                try:
                    rendered = text.format(**sig.params)
                except (KeyError, IndexError):
                    rendered = text
                descriptions.append(rendered)
            return f"Heute zwei Themen: {' und '.join(descriptions)}."
        else:
            return f"{len(mid)} kleinere Themen offen. Nichts brennt — wir nehmen's der Reihe nach."

    return "Alles ruhig. Ein paar Hinweise zum Festhalten, mehr nicht."


# ---------------------------------------------------------------------------
# 5. Policy-Gate-Checks (V4 Gates 1-4)
# ---------------------------------------------------------------------------

def check_consent_for_enrollment(
    student_is_minor: bool,
    consent_status: Optional[str],
) -> tuple[bool, Optional[str]]:
    """Gate 1 — Intake. Returns (allowed, reason_if_not)."""
    if not student_is_minor:
        return True, None
    if consent_status in ("all_valid", "consent_partial"):
        return True, None  # consent_partial: Operator wird informiert, aber Anmeldung läuft
    return False, "schule.consent_required_for_minors"


def check_instructor_license(
    instructor_has_license_for_course: bool,
) -> tuple[bool, Optional[str]]:
    """Gate 2 — Routing."""
    if instructor_has_license_for_course:
        return True, None
    return False, "schule.instructor_license_check"


def check_action_review_required(action: Action) -> bool:
    """Gate 3 — Action. In V1 immer True (Prinzip 11)."""
    return True


# ---------------------------------------------------------------------------
# 6. Hauptfunktion: Orchestrate
# ---------------------------------------------------------------------------

def orchestrate(
    request: OrchestrateRequest,
    signals: list[SchuleSignal],
) -> OrchestrateResponse:
    """
    Hauptfunktion. Wird von /schule/orchestrate Endpoint aufgerufen.

    In Produktion:
    - Signale aus DB laden (filter by school_id, status=open)
    - Pattern-Detection auf historischen Daten
    - SchoolState zusammenbauen
    - Sprache rendern

    Hier: Funktional, mit übergebenen Signalen für Tests.
    """
    patterns = detect_patterns(signals) if request.include_patterns else []
    actions = recommend_focus(signals) if request.include_recommendations else []
    summary = build_summary(signals, patterns)

    state = SchoolState(
        school_id=request.school_id,
        summary=summary,
        patterns=patterns,
        uncertainties=[],
        recommended_focus=actions,
        recent_signals=signals[:10],
        pattern_count=len(patterns),
        signal_count=len(signals),
        as_of=datetime.now(),
    )

    # Sprachausgabe für die Übersicht (UI-Top)
    top_language = LanguageOutput(
        mode="flow",
        text_key="schule.state.overview",
        params={"summary": summary},
        priority="medium",
    )

    return OrchestrateResponse(
        school_state=state,
        review_required=True,
        language=top_language,
    )


# ---------------------------------------------------------------------------
# 7. Compact Summary Endpoint (analog camp.shiksha summary)
# ---------------------------------------------------------------------------

def orchestrate_summary(
    school_id: str,
    signals: list[SchuleSignal],
) -> dict:
    """Kompakte Variante — nur 1 Satz Sprache, für mobile Quick-View."""
    patterns = detect_patterns(signals)
    summary = build_summary(signals, patterns)
    return {
        "school_id": school_id,
        "summary": summary,
        "signal_count": len(signals),
        "high_severity_count": len([s for s in signals if s.severity == "high"]),
        "as_of": datetime.now().isoformat(),
        "review_required": True,
    }


# ---------------------------------------------------------------------------
# 8. FastAPI Router (in main.py einbinden)
# ---------------------------------------------------------------------------

# Beispiel für main.py Integration:
"""
from fastapi import APIRouter
from schule_orchestrator import orchestrate, orchestrate_summary
from schule_models import OrchestrateRequest

schule_router = APIRouter(prefix="/schule", tags=["schule"])

@schule_router.post("/orchestrate")
async def schule_orchestrate(request: OrchestrateRequest):
    # Lade Signale aus DB
    signals = await load_signals_from_db(request.school_id)
    return orchestrate(request, signals)

@schule_router.post("/orchestrate/summary")
async def schule_orchestrate_summary(school_id: str):
    signals = await load_signals_from_db(school_id)
    return orchestrate_summary(school_id, signals)

# In main.py:
app.include_router(schule_router)
"""


__all__ = [
    "LANGUAGE_TEMPLATES",
    "render_language",
    "detect_patterns",
    "recommend_focus",
    "build_summary",
    "check_consent_for_enrollment",
    "check_instructor_license",
    "check_action_review_required",
    "orchestrate",
    "orchestrate_summary",
]
