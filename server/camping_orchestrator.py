"""
SHIKSHA · CAMPING.EDITION · Orchestrator V1
Stand: 25.04.2026

Verantwortung (analog SCHULE):
1. Signale aus DB sammeln und gewichten
2. Patterns erkennen (Stammgäste, no-show-Muster, Lieferanten-Pflege)
3. CampState zusammensetzen mit natürlich-sprachlicher Summary
4. Cross-Edition: Safeguarding-Signale konsumieren mit erhöhter Severity
5. Recommended Focus als Action-Vorschläge ausgeben (review_required)
"""

from datetime import datetime, date, timedelta
from typing import Optional

from camping_models import (
    Action, CampingOrchestrateRequest, CampingOrchestrateResponse, CampingSignal,
    CampState, LanguageOutput, Pattern, SafeguardingSignalRef,
)


# ---------------------------------------------------------------------------
# 1. Sprach-Vokabular (text_keys)
# ---------------------------------------------------------------------------

LANGUAGE_TEMPLATES: dict[str, dict[str, str]] = {
    "camping.reservation.payment_overdue": {
        "alert": "{guest} — Buchung verfällt {when}",
        "action": "{guest} an Anzahlung erinnern?",
        "flow":   "{guest} Anzahlung offen",
    },
    "camping.reservation.no_show_pattern": {
        "alert": "—",
        "action": "{guest} um Vorab-Bestätigung bitten?",
        "flow":   "{guest} bucht oft, kommt selten",
    },
    "camping.utility.unusual_consumption": {
        "alert": "—",
        "action": "Pitch {pitch} — beim Gast nachhören?",
        "flow":   "Pitch {pitch} Strom auffällig",
    },
    "camping.pitch.maintenance_overdue": {
        "alert": "—",
        "action": "Pitch {pitch} Schreiner anrufen?",
        "flow":   "Pitch {pitch} Wartung offen",
    },
    "camping.partnership.delivery_today": {
        "alert": "—",
        "action": "{supplier} bestätigen?",
        "flow":   "{supplier} bringt um {time}",
    },
    "camping.guest.silent_during_stay": {
        "alert": "—",
        "action": "Bei {guest} kurz vorbeischauen?",
        "flow":   "{guest} schweigt seit {days} Tagen",
    },
    "camping.weather.storm_warning": {
        "alert": "Sturm in {hours}h — handeln",
        "action": "Reisemobil-Gäste anschreiben?",
        "flow":   "Sturm {day}",
    },
    "camping.weather.rain_window": {
        "alert": "—",
        "action": "Indoor-Programm-Tipps verschicken?",
        "flow":   "Dauerregen {day}",
    },
    "camping.check_in.late_arrival": {
        "alert": "—",
        "action": "Späten Schlüssel-Plan vorbereiten?",
        "flow":   "{guest} kommt nach {time}",
    },
    "camping.safeguarding.pool_inspection_due": {
        "alert": "Pool-Inspektion in {days_left}",
        "action": "Termin Gesundheitsamt vereinbaren?",
        "flow":   "Pool-Prüfung naht",
    },
    "camping.safeguarding.pool_supervision": {
        "alert": "Pool ohne Aufsicht — sperren",
        "action": "{candidate} bitten einzuspringen?",
        "flow":   "Pool-Aufsicht heute lückig",
    },
    "camping.safeguarding.dog_repeat_complaint": {
        "alert": "—",
        "action": "Mit {guest} reden?",
        "flow":   "Hund {dog} — wiederholte Beschwerde",
    },
    "camping.journey.repeat_pattern": {
        "alert": "—",
        "action": "{guest} persönlich begrüßen?",
        "flow":   "{guest} — {season_count}. Saison",
    },
    "camping.behoerde.kurtaxe_overdue": {
        "alert": "Kurtaxe-Mahnung läuft",
        "action": "{amount} überweisen?",
        "flow":   "Kurtaxe {month} offen",
    },
    "camping.behoerde.tourismusabgabe_due": {
        "alert": "—",
        "action": "Tourismusabgabe {month} versenden?",
        "flow":   "Abgabe {month} steht an",
    },
    "camping.partnership.payment_overdue": {
        "alert": "—",
        "action": "{partner} bezahlen?",
        "flow":   "{partner} wartet auf Zahlung",
    },
    "camping.guest.pre_arrival_question": {
        "alert": "—",
        "action": "{guest} antworten?",
        "flow":   "{guest} fragt vor Anreise",
    },
}


# ---------------------------------------------------------------------------
# 2. Cross-Edition: Safeguarding-Severity-Erhöhung
# ---------------------------------------------------------------------------

# Safeguarding-Signale, die in CAMPING höhere Severity bekommen
# (Pool, Spielplatz, Aufsichtspflicht sind unmittelbarer als z.B. Yoga-Mattenraum)
CAMPING_SAFEGUARDING_BOOSTERS: dict[str, str] = {
    "safeguarding.pool_supervision_lueckig": "high",      # Pool ist unmittelbar lebensgefährlich
    "safeguarding.pool_inspection_due": "high",
    "safeguarding.playground_inspection_due": "mid",
    "safeguarding.background_check_expiring": "mid",
    "safeguarding.consent_missing": "mid",
    "safeguarding.dog_repeat_complaint": "mid",
    "safeguarding.incident_unresolved": "high",
}


def adjust_safeguarding_severity(signal_key: str, original: str) -> str:
    """Cross-Edition: CAMPING erhöht safeguarding-Severity bei kritischen Bereichen."""
    if signal_key in CAMPING_SAFEGUARDING_BOOSTERS:
        boost = CAMPING_SAFEGUARDING_BOOSTERS[signal_key]
        # Erhöhe nur, nicht senken
        order = ["info", "low", "mid", "high"]
        if order.index(boost) > order.index(original):
            return boost
    return original


# ---------------------------------------------------------------------------
# 3. Pattern-Erkennung
# ---------------------------------------------------------------------------

def detect_patterns(signals: list[CampingSignal]) -> list[Pattern]:
    """Wiederkehrende Signale, Stammgast-Muster, no-show-Muster."""
    by_key: dict[str, list[CampingSignal]] = {}
    for s in signals:
        by_key.setdefault(s.signal_key, []).append(s)

    patterns: list[Pattern] = []
    for key, group in by_key.items():
        if len(group) >= 2:
            confidence = min(0.5 + 0.15 * len(group), 0.95)
            polarity = group[0].polarity
            patterns.append(Pattern(
                pattern_key=f"pattern.{key}.recurring",
                description=f"{len(group)}x gesehen",
                confidence=confidence,
                related_signals=[str(s.id) for s in group if s.id],
                seen_count=len(group),
                first_seen=min((s.created_at for s in group), default=None),
                last_seen=max((s.created_at for s in group), default=None),
                polarity=polarity,
            ))

    # Spezielles Stammgast-Pattern
    repeat_signals = [s for s in signals if s.signal_key == "camping.journey.repeat_pattern"]
    if repeat_signals:
        patterns.append(Pattern(
            pattern_key="pattern.repeat_guests_growing",
            description=f"{len(repeat_signals)} Stammgäste in dieser Saison",
            confidence=0.85,
            related_signals=[str(s.id) for s in repeat_signals if s.id],
            seen_count=len(repeat_signals),
            polarity="positiv",
        ))

    return patterns


# ---------------------------------------------------------------------------
# 4. Recommended Focus
# ---------------------------------------------------------------------------

def recommend_focus(signals: list[CampingSignal], top_k: int = 3) -> list[Action]:
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
# 5. Summary-Generator (Sprache!)
# ---------------------------------------------------------------------------

def build_summary(signals: list[CampingSignal], patterns: list[Pattern]) -> str:
    """Erzeugt 1-2-Satz-Zusammenfassung im SHIKSHA-Stil."""
    if not signals:
        return "Heute ruhig. Keine offenen Themen."

    high = [s for s in signals if s.severity == "high"]
    mid = [s for s in signals if s.severity == "mid"]
    positive_patterns = [p for p in patterns if p.polarity == "positiv"]

    parts = []

    if high:
        if len(high) == 1:
            sig = high[0]
            templates = LANGUAGE_TEMPLATES.get(sig.signal_key, {})
            text = templates.get("alert", sig.signal_key)
            try:
                rendered = text.format(**sig.params)
            except (KeyError, IndexError):
                rendered = text
            parts.append(f"Achtung: {rendered}")
        else:
            parts.append(f"{len(high)} Sachen drücken")
    elif mid:
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
            parts.append(f"Heute: {' und '.join(descriptions)}")
        else:
            parts.append(f"{len(mid)} kleinere Themen offen, nichts brennt")

    # Positive Patterns hängen wir hinten an
    if positive_patterns:
        if len(positive_patterns) == 1:
            parts.append(f"sonst Erfreuliches: {positive_patterns[0].description}")

    return ". ".join(parts) + "." if parts else "Alles im grünen Bereich."


# ---------------------------------------------------------------------------
# 6. Occupancy-Berechnung (vereinfacht, V1)
# ---------------------------------------------------------------------------

def calculate_occupancy(running_stays: int, total_pitches: int) -> Optional[float]:
    if total_pitches == 0:
        return None
    return round(100.0 * running_stays / total_pitches, 1)


# ---------------------------------------------------------------------------
# 7. Hauptfunktion: Orchestrate
# ---------------------------------------------------------------------------

def orchestrate(
    request: CampingOrchestrateRequest,
    signals: list[CampingSignal],
    running_stays: int = 0,
    total_pitches: int = 0,
) -> CampingOrchestrateResponse:
    patterns = detect_patterns(signals) if request.include_patterns else []
    actions = recommend_focus(signals) if request.include_recommendations else []
    summary = build_summary(signals, patterns)
    occupancy = calculate_occupancy(running_stays, total_pitches)

    state = CampState(
        campsite_id=request.campsite_id,
        summary=summary,
        patterns=patterns,
        uncertainties=[],
        recommended_focus=actions,
        recent_signals=signals[:10],
        pattern_count=len(patterns),
        signal_count=len(signals),
        occupancy_pct=occupancy,
        as_of=datetime.now(),
    )

    top_language = LanguageOutput(
        mode="flow",
        text_key="camping.state.overview",
        params={"summary": summary},
        priority="medium",
    )

    return CampingOrchestrateResponse(
        camp_state=state,
        review_required=True,
        language=top_language,
    )


# ---------------------------------------------------------------------------
# 8. Compact Summary
# ---------------------------------------------------------------------------

def orchestrate_summary(
    campsite_id: str,
    signals: list[CampingSignal],
) -> dict:
    patterns = detect_patterns(signals)
    summary = build_summary(signals, patterns)
    return {
        "campsite_id": campsite_id,
        "summary": summary,
        "signal_count": len(signals),
        "high_severity_count": len([s for s in signals if s.severity == "high"]),
        "as_of": datetime.now().isoformat(),
        "review_required": True,
    }


# ---------------------------------------------------------------------------
# 9. Policy-Gate-Checks
# ---------------------------------------------------------------------------

def check_no_auto_rebooking(action: str) -> tuple[bool, Optional[str]]:
    """Gate 3 — Pitch-Wechsel braucht immer Operator-Bestätigung."""
    if action in ("pitch_change", "pitch_swap", "pitch_reassign"):
        return False, "camping.no_auto_rebooking"
    return True, None


def check_minor_supervision(persons: int, minors_count: int) -> tuple[bool, Optional[str]]:
    """Gate 1 — Reservierung mit Minderjährigen ohne Erwachsene."""
    if minors_count > 0 and persons - minors_count == 0:
        return False, "camping.minor_supervision_required"
    return True, None


def check_review_request_allowed() -> tuple[bool, Optional[str]]:
    """Gate 3 — Bewertungs-Bitten gehen NIE automatisch."""
    return False, "camping.no_auto_review_request"


__all__ = [
    "LANGUAGE_TEMPLATES",
    "CAMPING_SAFEGUARDING_BOOSTERS",
    "adjust_safeguarding_severity",
    "detect_patterns",
    "recommend_focus",
    "build_summary",
    "calculate_occupancy",
    "orchestrate",
    "orchestrate_summary",
    "check_no_auto_rebooking",
    "check_minor_supervision",
    "check_review_request_allowed",
]
