"""
SHIKSHA · Safeguarding Nightly Learning Cron
Stand: 25.04.2026

Tägliches Lern-Script — läuft im Hintergrund, lernt aus Signalen.

Cron-Eintrag:
    crontab -e
    # Zeile hinzufügen:
    0 3 * * * /opt/shiksha/venv/bin/python /opt/shiksha/safeguarding_cron.py >> /var/log/shiksha-safeguarding.log 2>&1

Ablauf:
1. Lade alle safeguarding_signals der letzten 36 Monate
2. Detektiere Pattern-Kandidaten (4 Lernmodi)
3. Schreibe neue Kandidaten in safeguarding_pattern_candidates (UPSERT)
4. Aktualisiere Severity-Feedback-Aggregate
5. Berechne Severity-Vorschläge (≥ 50 Vorkommen)
6. Cleanup: Anonymisiere Daten älter als 36 Monate (Retention-Pflicht)
7. Loggt Statistik

Niemals: aktiviert Pattern selbst — nur Operator promotet.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

# Pfad zu safeguarding-Modulen
sys.path.insert(0, "/opt/shiksha")
try:
    from safeguarding_models import SafeguardingSignal, PatternCandidate, SeverityFeedback
    from safeguarding_orchestrator import (
        run_learning_pass,
        record_feedback,
        compute_severity_proposal,
        RESOLUTION_SCORES,
    )
except ImportError:
    # Fallback für lokale Entwicklung
    sys.path.insert(0, str(Path(__file__).parent.parent / "safeguarding" / "server"))
    from safeguarding_models import SafeguardingSignal, PatternCandidate, SeverityFeedback
    from safeguarding_orchestrator import (
        run_learning_pass,
        record_feedback,
        compute_severity_proposal,
        RESOLUTION_SCORES,
    )


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

LOOKBACK_DAYS = 36 * 30  # 36 Monate
RETENTION_DAYS = 36 * 30
TARGET_EDITIONS = ["schule.shiksha", "camping.shiksha", "club.shiksha"]


def get_db_connection():
    """Verbindet mit der Production-DB via DATABASE_URL (env-driven)."""
    from database import DATABASE_URL  # delayed import (Cron-Standalone)
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def log(msg, level="INFO"):
    print(f"[{level}] {datetime.now().isoformat()} — {msg}", flush=True)


# ---------------------------------------------------------------------------
# 1. Signale laden
# ---------------------------------------------------------------------------

def load_recent_signals(conn, days: int = LOOKBACK_DAYS) -> list[SafeguardingSignal]:
    cutoff = datetime.now() - timedelta(days=days)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, organization_id, organization_type, edition, signal_key, severity,
               params, related_person_id, related_entity, status,
               created_at, resolved_at, resolved_by, resolution_action
        FROM safeguarding_signals
        WHERE created_at >= %s
        ORDER BY created_at DESC
    """, (cutoff,))

    signals = []
    for row in cur.fetchall():
        signals.append(SafeguardingSignal(
            id=row["id"],
            organization_id=row.get("organization_id"),
            organization_type=row.get("organization_type"),
            edition=row.get("edition"),
            signal_key=row["signal_key"],
            severity=row.get("severity", "mid"),
            params=row.get("params") or {},
            related_person_id=row.get("related_person_id"),
            related_entity=row.get("related_entity") or {},
            status=row.get("status", "open"),
            created_at=row["created_at"],
            resolved_at=row.get("resolved_at"),
            resolved_by=row.get("resolved_by"),
            resolution_action=row.get("resolution_action"),
        ))
    return signals


# ---------------------------------------------------------------------------
# 2. Pattern-Kandidaten persistieren
# ---------------------------------------------------------------------------

def upsert_pattern_candidates(conn, candidates: list[PatternCandidate]):
    cur = conn.cursor()
    inserted = 0
    updated = 0
    for c in candidates:
        cur.execute("""
            INSERT INTO safeguarding_pattern_candidates
                (pattern_type, pattern_key, description, confidence, occurrences,
                 related_signal_keys, related_entities, applicable_editions,
                 suggested_action, first_seen, last_seen, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            ON CONFLICT (pattern_key) DO UPDATE SET
                confidence = EXCLUDED.confidence,
                occurrences = EXCLUDED.occurrences,
                last_seen = EXCLUDED.last_seen,
                description = EXCLUDED.description
            WHERE safeguarding_pattern_candidates.status = 'pending'
            RETURNING (xmax = 0) AS inserted_now
        """, (
            c.pattern_type, c.pattern_key, c.description, c.confidence, c.occurrences,
            c.related_signal_keys, Json(c.related_entities), c.applicable_editions,
            c.suggested_action, c.first_seen, c.last_seen,
        ))
        row = cur.fetchone()
        if row and row.get("inserted_now"):
            inserted += 1
        else:
            updated += 1

    return inserted, updated


# ---------------------------------------------------------------------------
# 3. Severity-Feedback aggregieren
# ---------------------------------------------------------------------------

def update_severity_feedback(conn) -> dict:
    """Aktualisiert Aggregate für alle resolved Signale seit letztem Lauf."""
    cur = conn.cursor()
    cur.execute("""
        SELECT signal_key, severity, resolution_action, count(*) AS cnt
        FROM safeguarding_signals
        WHERE status = 'resolved'
          AND resolution_action IS NOT NULL
        GROUP BY signal_key, severity, resolution_action
    """)

    aggregates: dict[str, SeverityFeedback] = {}
    for row in cur.fetchall():
        signal_key = row["signal_key"]
        if signal_key not in aggregates:
            aggregates[signal_key] = SeverityFeedback(
                signal_key=signal_key,
                current_default_severity=row.get("severity", "mid"),
                feedback_count=0,
                feedback_score_sum=0.0,
            )
        score = RESOLUTION_SCORES.get(row["resolution_action"], 0.0)
        aggregates[signal_key].feedback_count += row["cnt"]
        aggregates[signal_key].feedback_score_sum += score * row["cnt"]
        aggregates[signal_key].last_resolution_at = datetime.now()

    proposals = {}
    for signal_key, agg in aggregates.items():
        proposal = compute_severity_proposal(agg)

        cur.execute("""
            INSERT INTO safeguarding_severity_feedback
                (signal_key, current_default_severity, feedback_count, feedback_score_sum,
                 proposed_severity, proposed_at, last_resolution_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (signal_key) DO UPDATE SET
                feedback_count = EXCLUDED.feedback_count,
                feedback_score_sum = EXCLUDED.feedback_score_sum,
                proposed_severity = EXCLUDED.proposed_severity,
                proposed_at = EXCLUDED.proposed_at,
                last_resolution_at = EXCLUDED.last_resolution_at
        """, (
            agg.signal_key,
            agg.current_default_severity,
            agg.feedback_count,
            agg.feedback_score_sum,
            proposal,
            datetime.now() if proposal else None,
            agg.last_resolution_at,
        ))

        if proposal:
            proposals[signal_key] = (agg.current_default_severity, proposal)

    return proposals


# ---------------------------------------------------------------------------
# 4. Retention: Anonymisierung alter Daten
# ---------------------------------------------------------------------------

def apply_retention(conn) -> int:
    """Anonymisiert Signale älter als RETENTION_DAYS — keine Löschung, Audit-Spur bleibt."""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    cur = conn.cursor()
    cur.execute("""
        UPDATE safeguarding_signals
        SET related_person_id = NULL,
            params = '{}'::jsonb,
            resolved_by = NULL
        WHERE created_at < %s
          AND related_person_id IS NOT NULL
        RETURNING id
    """, (cutoff,))
    return cur.rowcount


# ---------------------------------------------------------------------------
# 5. Hauptfunktion
# ---------------------------------------------------------------------------

def main():
    log("Safeguarding Nightly Learning Pass — Start")

    try:
        conn = get_db_connection()
    except Exception as e:
        log(f"DB-Verbindung fehlgeschlagen: {e}", level="ERROR")
        return 1

    try:
        # 1. Signale laden
        signals = load_recent_signals(conn)
        log(f"  Signale geladen: {len(signals)}")

        if not signals:
            log("  Keine Signale — Pass wird übersprungen.")
            return 0

        # 2. Lern-Pass
        result = run_learning_pass(signals, target_editions=TARGET_EDITIONS)
        all_candidates = (
            [PatternCandidate(**c) for c in result["frequency_cluster_candidates"]]
            + [PatternCandidate(**c) for c in result["seasonal_candidates"]]
            + [PatternCandidate(**c) for c in result["cross_edition_candidates"]]
        )
        log(f"  Lern-Pass abgeschlossen: {result['candidates_total']} Kandidaten")
        log(f"    Frequency: {len(result['frequency_cluster_candidates'])}")
        log(f"    Seasonal:  {len(result['seasonal_candidates'])}")
        log(f"    Cross-Ed:  {len(result['cross_edition_candidates'])}")

        # 3. Persistieren
        inserted, updated = upsert_pattern_candidates(conn, all_candidates)
        log(f"  Persistiert: {inserted} neu, {updated} aktualisiert")

        # 4. Severity-Feedback
        proposals = update_severity_feedback(conn)
        log(f"  Severity-Vorschläge: {len(proposals)}")
        for key, (from_sev, to_sev) in proposals.items():
            log(f"    {key}: {from_sev} → {to_sev}")

        # 5. Retention
        anonymized = apply_retention(conn)
        log(f"  Retention angewandt: {anonymized} Signale anonymisiert")

        conn.commit()
        log("Lern-Pass erfolgreich abgeschlossen.")
        return 0

    except Exception as e:
        conn.rollback()
        log(f"Fehler im Lern-Pass: {e}", level="ERROR")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
