"""
SHIKSHA · SAFEGUARDING ORCHESTRATOR · Lernfähig V1
Stand: 25.04.2026

Vier Lernmodi (siehe BUILD_PACK section 2):
1. Pattern-Lernen aus Frequenz-Cluster
2. Saisonale Patterns
3. Cross-Edition-Hinweise
4. Severity-Adjustment aus Operator-Feedback

Architektur-Prinzipien:
- Keine ML-Libraries — alles in Python rekonstruierbar
- Pattern erst aktiv nach Operator-Promotion (V4-Prinzip 7 + CLUB-Architektur)
- Severity-Anpassung braucht > 50 Vorkommen + signifikantes Feedback-Signal
- Modul kommuniziert nie mit Endkunden direkt
"""

from collections import defaultdict, Counter
from datetime import datetime, date, timedelta
from typing import Optional

from safeguarding_models import (
    PatternCandidate, PromotedPattern, SafeguardingSignal,
    SeverityFeedback, CrossEditionHint, IncidentReport,
)


# ---------------------------------------------------------------------------
# 1. Sprach-Vokabular (text_keys)
# ---------------------------------------------------------------------------

LANGUAGE_TEMPLATES: dict[str, dict[str, str]] = {
    "safeguarding.background_check_expiring": {
        "alert": "{person} Führungszeugnis endet morgen",
        "action": "{person} an Erneuerung erinnern?",
        "flow":   "{person} Führungszeugnis läuft",
    },
    "safeguarding.consent_missing": {
        "alert": "{person} darf nicht {context}",
        "action": "{guardian} um {type} bitten?",
        "flow":   "{person} Konsent {type} fehlt",
    },
    "safeguarding.pool_inspection_due": {
        "alert": "Pool-Prüfung in {days_left} Tagen",
        "action": "Termin Gesundheitsamt vereinbaren?",
        "flow":   "Pool-Prüfung naht",
    },
    "safeguarding.pool_supervision_lueckig": {
        "alert": "Pool ohne Aufsicht — sperren",
        "action": "{candidate} bitten einzuspringen?",
        "flow":   "Pool-Aufsicht lückig",
    },
    "safeguarding.dog_repeat_complaint": {
        "alert": "—",
        "action": "Mit {guest} reden?",
        "flow":   "Hund {dog} — wiederholte Beschwerde",
    },
    "safeguarding.incident_unresolved": {
        "alert": "Vorfall {id} braucht Antwort",
        "action": "Status klären + dokumentieren?",
        "flow":   "Vorfall offen seit {days}",
    },
}


# ---------------------------------------------------------------------------
# 2. Pattern-Detection: Frequenz-Cluster
# ---------------------------------------------------------------------------

FREQ_CLUSTER_MIN_OCCURRENCES = 3
FREQ_CLUSTER_WINDOW_DAYS = 365


def detect_frequency_cluster_candidates(
    signals: list[SafeguardingSignal],
    min_occurrences: int = FREQ_CLUSTER_MIN_OCCURRENCES,
    window_days: int = FREQ_CLUSTER_WINDOW_DAYS,
) -> list[PatternCandidate]:
    """
    Erkennt: gleicher signal_key, mehrfach, im definierten Zeitfenster.
    Wenn related_entity matchen (gleiche Person/Pitch/Hund), wird das im Pattern-Key reflektiert.
    """
    cutoff = datetime.now() - timedelta(days=window_days)
    recent = [s for s in signals if s.created_at >= cutoff]

    by_key: dict[str, list[SafeguardingSignal]] = defaultdict(list)
    for s in recent:
        by_key[s.signal_key].append(s)

    candidates: list[PatternCandidate] = []
    for signal_key, group in by_key.items():
        if len(group) < min_occurrences:
            continue

        # Versuche Entity-Matching
        entity_groups = group_by_entity(group)
        for entity_id, entity_group in entity_groups.items():
            if len(entity_group) >= min_occurrences:
                pattern_key = (
                    f"{signal_key}.recurring_entity_{entity_id}"
                    if entity_id else f"{signal_key}.recurring"
                )
                confidence = min(0.5 + 0.12 * len(entity_group), 0.95)
                candidates.append(PatternCandidate(
                    pattern_type="recurring_entity" if entity_id else "frequency_cluster",
                    pattern_key=pattern_key,
                    description=f"{signal_key} {len(entity_group)}× innerhalb {window_days} Tagen"
                                + (f" — gleiche Entity {entity_id}" if entity_id else ""),
                    confidence=confidence,
                    occurrences=len(entity_group),
                    related_signal_keys=[signal_key],
                    related_entities={"entity_id": entity_id} if entity_id else {},
                    first_seen=min(s.created_at for s in entity_group),
                    last_seen=max(s.created_at for s in entity_group),
                    status="pending",
                ))
    return candidates


def group_by_entity(signals: list[SafeguardingSignal]) -> dict[Optional[str], list[SafeguardingSignal]]:
    """Gruppiert Signale nach related_person_id oder related_entity-Hauptschlüssel."""
    groups: dict[Optional[str], list[SafeguardingSignal]] = defaultdict(list)
    for s in signals:
        # primär related_person_id
        key = s.related_person_id
        if not key and s.related_entity:
            # Falls dict, nimm ersten Wert als pseudo-Key
            try:
                key = next(iter(s.related_entity.values()))
            except StopIteration:
                key = None
        groups[key].append(s)
    return dict(groups)


# ---------------------------------------------------------------------------
# 3. Pattern-Detection: Saisonal
# ---------------------------------------------------------------------------

SEASONAL_TOLERANCE_DAYS = 30
SEASONAL_MIN_YEARS = 2


def detect_seasonal_candidates(
    signals: list[SafeguardingSignal],
    tolerance_days: int = SEASONAL_TOLERANCE_DAYS,
    min_years: int = SEASONAL_MIN_YEARS,
) -> list[PatternCandidate]:
    """
    Erkennt: derselbe signal_key tritt jährlich in einem ähnlichen Zeitfenster auf.
    Mindestens 2 Jahre, sonst Zufall.
    """
    by_key: dict[str, list[SafeguardingSignal]] = defaultdict(list)
    for s in signals:
        by_key[s.signal_key].append(s)

    candidates: list[PatternCandidate] = []
    for signal_key, group in by_key.items():
        # Gruppiere nach Jahr, behalte für jedes Jahr den ersten/typischen Tag-of-Year
        by_year: dict[int, list[int]] = defaultdict(list)
        for s in group:
            by_year[s.created_at.year].append(s.created_at.timetuple().tm_yday)

        if len(by_year) < min_years:
            continue

        # Prüfe ob die day_of_year ähnlich sind über die Jahre
        year_first_doys = [min(doys) for doys in by_year.values()]
        if not year_first_doys:
            continue

        median_doy = sorted(year_first_doys)[len(year_first_doys) // 2]
        within_tol = sum(1 for d in year_first_doys if abs(d - median_doy) <= tolerance_days)

        if within_tol >= min_years:
            pattern_key = f"{signal_key}.seasonal"
            confidence = min(0.55 + 0.1 * within_tol, 0.9)
            month_label = month_name_for_doy(median_doy)
            candidates.append(PatternCandidate(
                pattern_type="seasonal",
                pattern_key=pattern_key,
                description=f"{signal_key} tritt jährlich um {month_label} auf ({within_tol} Jahre Bestätigung)",
                confidence=confidence,
                occurrences=len(group),
                related_signal_keys=[signal_key],
                first_seen=min(s.created_at for s in group),
                last_seen=max(s.created_at for s in group),
                suggested_action=f"Bei nächstem Anlauf 30 Tage vor {month_label} Vorbereitung beginnen",
                status="pending",
            ))
    return candidates


def month_name_for_doy(doy: int) -> str:
    """day-of-year → grobes Monatslabel auf Deutsch."""
    months_de = ["Januar", "Februar", "März", "April", "Mai", "Juni",
                 "Juli", "August", "September", "Oktober", "November", "Dezember"]
    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    cum = 0
    for i, d in enumerate(days_per_month):
        cum += d
        if doy <= cum:
            return months_de[i]
    return "Dezember"


# ---------------------------------------------------------------------------
# 4. Pattern-Detection: Cross-Edition
# ---------------------------------------------------------------------------

CROSS_EDITION_RATIO_THRESHOLD = 0.3   # 30% Auftritts-Rate genügt für Cross-Edition-Hinweis


def detect_cross_edition_candidates(
    signals: list[SafeguardingSignal],
    target_editions: list[str],
) -> list[PatternCandidate]:
    """
    Erkennt: ein signal_key tritt in einer Edition häufig auf — Hinweis an die anderen Editionen,
    dass das auch dort relevant sein könnte.
    """
    if len(signals) < 30:
        return []

    by_edition_key: dict[tuple[str, str], int] = Counter()
    by_edition: dict[str, int] = Counter()
    for s in signals:
        if s.edition:
            by_edition_key[(s.edition, s.signal_key)] += 1
            by_edition[s.edition] += 1

    candidates: list[PatternCandidate] = []
    for (source_edition, signal_key), count in by_edition_key.items():
        if by_edition[source_edition] == 0:
            continue
        ratio = count / by_edition[source_edition]
        if ratio >= CROSS_EDITION_RATIO_THRESHOLD and count >= 10:
            other_editions = [e for e in target_editions if e != source_edition]
            if not other_editions:
                continue
            pattern_key = f"{signal_key}.cross_edition_from_{source_edition}"
            candidates.append(PatternCandidate(
                pattern_type="cross_edition",
                pattern_key=pattern_key,
                description=f"{signal_key} ist in {source_edition} häufig ({int(ratio*100)}% der Signale, {count}×) — könnte auch in {','.join(other_editions)} relevant sein",
                confidence=min(0.4 + ratio, 0.85),
                occurrences=count,
                related_signal_keys=[signal_key],
                applicable_editions=other_editions,
                suggested_action=f"Übertragung als info-Signal in Edition(en): {', '.join(other_editions)}",
                status="pending",
            ))
    return candidates


# ---------------------------------------------------------------------------
# 5. Severity-Feedback-Loop
# ---------------------------------------------------------------------------

# Score je Resolution-Action (siehe BUILD_PACK section 2.2)
RESOLUTION_SCORES: dict[str, float] = {
    "resolved_immediately": 1.0,
    "resolved_within_24h": 0.0,
    "resolved_late": -0.5,
    "dismissed": -2.0,
    "escalated": 2.0,
}

SEVERITY_ADJUST_MIN_FEEDBACK = 50
SEVERITY_ADJUST_MEAN_THRESHOLD = 0.7


def record_feedback(
    feedback_aggregate: SeverityFeedback,
    resolution_action: str,
) -> SeverityFeedback:
    """Aktualisiert Aggregat eines signal_keys mit einer neuen Resolution."""
    score = RESOLUTION_SCORES.get(resolution_action, 0.0)
    feedback_aggregate.feedback_count += 1
    feedback_aggregate.feedback_score_sum += score
    feedback_aggregate.last_resolution_at = datetime.now()
    return feedback_aggregate


def compute_severity_proposal(
    aggregate: SeverityFeedback,
) -> Optional[str]:
    """
    Berechnet, ob eine Severity-Anpassung vorgeschlagen werden soll.
    Schwelle: ≥ 50 Vorkommen + |mean_score| > 0.7.
    """
    if aggregate.feedback_count < SEVERITY_ADJUST_MIN_FEEDBACK:
        return None

    mean = aggregate.mean_score
    if abs(mean) < SEVERITY_ADJUST_MEAN_THRESHOLD:
        return None

    severity_order = ["info", "low", "mid", "high"]
    current_idx = severity_order.index(aggregate.current_default_severity)

    # mean > 0 → eskaliert oder schnell gelöst → höher priorisieren
    # mean < 0 → wird oft dismissed oder spät gelöst → senken
    direction = 1 if mean > 0 else -1
    new_idx = max(0, min(len(severity_order) - 1, current_idx + direction))

    if new_idx == current_idx:
        return None

    return severity_order[new_idx]


# ---------------------------------------------------------------------------
# 6. Promotion / Dismiss
# ---------------------------------------------------------------------------

def promote_candidate_to_pattern(
    candidate: PatternCandidate,
    promoted_by: str,
    fires_signal: Optional[str] = None,
    fires_severity: str = "mid",
    affecting_organizations: Optional[list[dict]] = None,
) -> PromotedPattern:
    """Wandelt Pattern-Kandidat in aktiven Pattern um."""
    return PromotedPattern(
        candidate_id=candidate.id,
        pattern_key=candidate.pattern_key,
        description=candidate.description,
        pattern_type=candidate.pattern_type,
        active_since=datetime.now(),
        fires_signal=fires_signal or candidate.related_signal_keys[0] if candidate.related_signal_keys else None,
        fires_severity=fires_severity,  # type: ignore
        affecting_organizations=affecting_organizations or [],
    )


def dismiss_candidate(
    candidate: PatternCandidate,
    dismissed_by: str,
    reason: Optional[str] = None,
) -> PatternCandidate:
    """Markiert Kandidat als verworfen — bleibt zur Audit-Spur in DB."""
    candidate.status = "dismissed"
    candidate.dismissed_at = datetime.now()
    candidate.dismissed_by = dismissed_by
    if reason:
        candidate.metadata["dismiss_reason"] = reason
    return candidate


# ---------------------------------------------------------------------------
# 7. Cross-Edition Signal-Bridge
# ---------------------------------------------------------------------------

def emit_cross_edition_hint(
    pattern: PromotedPattern,
    target_editions: list[str],
    hint_text_key: str = "safeguarding.cross_edition.hint",
) -> list[CrossEditionHint]:
    """Erzeugt Cross-Edition-Hinweise für jede Ziel-Edition."""
    hints = []
    source_edition = pattern.metadata.get("source_edition", "unknown")
    for target in target_editions:
        if target == source_edition:
            continue
        hints.append(CrossEditionHint(
            source_edition=source_edition,
            target_edition=target,
            pattern_key=pattern.pattern_key,
            hint_text_key=hint_text_key,
        ))
    return hints


# ---------------------------------------------------------------------------
# 8. Hauptfunktion: vollständiger Lern-Pass (Cron-fähig)
# ---------------------------------------------------------------------------

def run_learning_pass(
    signals: list[SafeguardingSignal],
    target_editions: list[str],
) -> dict:
    """
    Führt alle vier Lernmodi durch.
    Wird typischerweise als Cron-Job 1×/24h ausgeführt.
    Output: was würde dem Operator zur Promotion vorgeschlagen werden?
    """
    freq_candidates = detect_frequency_cluster_candidates(signals)
    seasonal_candidates = detect_seasonal_candidates(signals)
    cross_candidates = detect_cross_edition_candidates(signals, target_editions)

    return {
        "ran_at": datetime.now().isoformat(),
        "candidates_total": len(freq_candidates) + len(seasonal_candidates) + len(cross_candidates),
        "frequency_cluster_candidates": [c.model_dump() for c in freq_candidates],
        "seasonal_candidates": [c.model_dump() for c in seasonal_candidates],
        "cross_edition_candidates": [c.model_dump() for c in cross_candidates],
    }


# ---------------------------------------------------------------------------
# 9. Render Sprache
# ---------------------------------------------------------------------------

def render_language(signal: SafeguardingSignal, mode: str = "flow") -> dict:
    templates = LANGUAGE_TEMPLATES.get(signal.signal_key, {})
    text = templates.get(mode, signal.signal_key)
    try:
        rendered = text.format(**signal.params)
    except (KeyError, IndexError):
        rendered = text
    return {
        "mode": mode,
        "text_key": signal.signal_key,
        "params": signal.params,
        "rendered": rendered,
        "priority": "high" if signal.severity == "high" else "medium" if signal.severity == "mid" else "low",
    }


__all__ = [
    "LANGUAGE_TEMPLATES",
    "FREQ_CLUSTER_MIN_OCCURRENCES",
    "SEASONAL_TOLERANCE_DAYS",
    "RESOLUTION_SCORES",
    "SEVERITY_ADJUST_MIN_FEEDBACK",
    "detect_frequency_cluster_candidates",
    "detect_seasonal_candidates",
    "detect_cross_edition_candidates",
    "record_feedback",
    "compute_severity_proposal",
    "promote_candidate_to_pattern",
    "dismiss_candidate",
    "emit_cross_edition_hint",
    "run_learning_pass",
    "render_language",
]
