"""Calendar — Query-Building, Berechtigung, Stats, virtuelle Geburtstage.

Lebt im services-Layer, damit Router-Code dünn bleibt und alle Berechtigungs-
Logik an einer Stelle testbar ist.

Konventionen aus SHIKSHA_CALENDAR_SPEC.md §6 (Berechtigung), §4.6 (Geburtstage),
§10 (Stats).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Query, Session

from shiksha_engine.models.event import (
    EVENT_TYPES_BY_EDITION,
    Event,
    VIRTUAL_EVENT_TYPES,
)
from shiksha_engine.models.operator import Operator
from shiksha_engine.models.organization import Organization
from shiksha_engine.models.person import Person


def _tenant_tz(db: Session, tenant_org_id: str) -> ZoneInfo:
    """Liefert Tenant-TZ (Default UTC wenn Org unbekannt). T-009-Fix."""
    org = db.query(Organization).filter_by(id=tenant_org_id).first()
    return ZoneInfo(org.timezone) if org and org.timezone else ZoneInfo("UTC")


# ---------------------------------------------------------- Berechtigung


def _is_developer(op: Operator) -> bool:
    return op.kind == "system" or op.role == "developer"


def _is_staff_role(op: Operator) -> bool:
    """leitung / padagogin / paedagogin / sonstige Staff-Rollen."""
    return op.role in ("leitung", "padagoge", "padagogin", "paedagogin")


def _is_klient_role(op: Operator) -> bool:
    """eltern / teilnehmer — read-only, eingeschränkter Filter."""
    return op.role in ("eltern", "teilnehmer")


def apply_read_filter(
    db: Session,
    query: Query,
    operator: Operator,
    target_tenant: str,
) -> Query:
    """Wendet rollen-spezifische Read-Filter auf eine Event-Query an.

    - developer / leitung: alles im target_tenant
    - padagogin: alles im Tenant, MINUS Urlaub mit status!=approved von anderen
    - eltern / teilnehmer: nur "betreffende" Events (siehe Spec §6.2)
    """
    # Tenant-Isolation immer
    query = query.filter(
        Event.tenant_org_id == target_tenant,
        Event.deleted_at.is_(None),
    )

    if _is_developer(operator) or operator.role == "leitung":
        return query

    if _is_staff_role(operator):
        # Urlaub-Privacy: pending/rejected vom anderen Antragsteller ausblenden
        query = query.filter(
            or_(
                Event.event_type != "urlaub",
                Event.metadata_["status"].astext == "approved",
                Event.metadata_["status"].astext.is_(None),  # legacy ohne status
                Event.operator_id == operator.id,
            )
        )
        return query

    if _is_klient_role(operator):
        # Vereinfachte Phase-1-Logik: ohne Operator-↔-Person-Link sehen
        # Eltern/Teilnehmer nur GLOBALE Termine (keine Participants).
        # Phase 2 mit T-003: eigene_person_ids in Participants.
        query = query.filter(
            and_(
                Event.event_type == "termin",
                func.jsonb_array_length(Event.participants) == 0,
            )
        )
        return query

    # Unbekannte Rolle → keine Events
    return query.filter(False)


def can_create(operator: Operator, payload_event_type: str) -> bool:
    if _is_developer(operator) or operator.role == "leitung":
        return True
    if _is_staff_role(operator):
        # Pädagogin: kein Urlaub-anlegen für andere (Urlaub geht über Leitung in Phase 2)
        return payload_event_type in ("termin", "kurs", "abwesenheit")
    return False


def can_modify(operator: Operator, event: Event) -> bool:
    if _is_developer(operator) or operator.role == "leitung":
        return True
    if _is_staff_role(operator):
        return event.operator_id == operator.id
    return False


def can_delete(operator: Operator, event: Event) -> bool:
    # Identisch zu can_modify in Phase 1
    return can_modify(operator, event)


# ---------------------------------------------------------- Repeat-Expansion


def expand_repeat(
    base_start: datetime,
    base_end: datetime | None,
    kind: str,  # "daily" | "weekly" | "monthly"
    count: int,
) -> list[tuple[datetime, datetime | None, int]]:
    """Erzeugt N (start, end, index) Tupel für client-side multi-insert.

    index ist 1-basiert. Erstes Tupel ist die Ausgangszeit (index=1).
    """
    if count < 1:
        return []
    out: list[tuple[datetime, datetime | None, int]] = []
    for i in range(count):
        if kind == "daily":
            delta = timedelta(days=i)
        elif kind == "weekly":
            delta = timedelta(weeks=i)
        elif kind == "monthly":
            # naiv: jeweils +30 Tage; präzise Monatsarithmetik ist Phase 2
            delta = timedelta(days=30 * i)
        else:
            raise ValueError(f"Unbekannter repeat.kind: {kind}")
        start = base_start + delta
        end = base_end + delta if base_end else None
        out.append((start, end, i + 1))
    return out


def fresh_recurrence_group() -> str:
    return str(uuid4())


# ---------------------------------------------------------- Virtuelle Geburtstage


def get_birthday_events(
    db: Session,
    tenant_org_id: str,
    from_at: datetime,
    to_at: datetime,
    operator: Operator,
) -> list[dict[str, Any]]:
    """Liefert virtuelle Geburtstags-Events im Zeitfenster.

    Berechtigung (Spec §4.6 + §6):
    - leitung / padagogin / developer: alle aktiven Personen mit birth_date
    - eltern / teilnehmer: in Phase 1 keine Geburtstage (kommt mit T-003)
    """
    if _is_klient_role(operator):
        return []  # Phase 1: kein Operator-↔-Person-Link

    persons = (
        db.query(Person)
        .filter(
            Person.tenant_org_id == tenant_org_id,
            Person.deleted_at.is_(None),
            Person.active.is_(True),
            Person.birth_date.isnot(None),
        )
        .all()
    )

    results: list[dict[str, Any]] = []
    from_date = from_at.date()
    to_date = to_at.date()

    for p in persons:
        bd = p.birth_date
        # Geburtstage im Fensterjahr berechnen — alle Jahre, in denen der
        # Tag.Monat ins (from, to)-Fenster fällt.
        for year in range(from_date.year, to_date.year + 1):
            try:
                candidate = date(year, bd.month, bd.day)
            except ValueError:
                # 29.02. in Nicht-Schaltjahr: auf 28.02. schieben
                candidate = date(year, bd.month, 28)
            if from_date <= candidate <= to_date:
                age = year - bd.year
                results.append({
                    "id": None,  # synthetic
                    "event_type": "geburtstag",
                    "title": f"Geburtstag · {p.given_name} {p.family_name or ''}".strip(),
                    "start_at": datetime.combine(candidate, time(0, 0), tzinfo=timezone.utc),
                    "end_at": None,
                    "all_day": True,
                    "location": None,
                    "participants": [p.id],
                    "subtype": None,
                    "urgency": "normal",
                    "status": "approved",
                    "synthetic": True,
                    "metadata": {
                        "synthetic": True,
                        "person_id": p.id,
                        "person_age": age,
                    },
                })
    return results


# ---------------------------------------------------------- Stats


def compute_event_stats(
    db: Session, tenant_org_id: str, operator: Operator
) -> dict[str, Any]:
    """EventStats — Übersicht für UI-Stats-Line. Respektiert Read-Filter."""
    base = apply_read_filter(db, db.query(Event), operator, tenant_org_id)

    total = base.count()

    # heute (Tenant-TZ — T-009-Fix, vorher UTC mit 2h-Drift-Window nach Mitternacht)
    tz = _tenant_tz(db, tenant_org_id)
    now = datetime.now(tz=tz)
    today_start = datetime.combine(now.date(), time(0, 0), tzinfo=tz)
    today_end = today_start + timedelta(days=1)
    today = base.filter(
        Event.start_at >= today_start, Event.start_at < today_end
    ).count()

    # Diese Woche (Mo–So, in Tenant-TZ)
    monday = today_start - timedelta(days=now.weekday())
    sunday_end = monday + timedelta(days=7)
    this_week = base.filter(
        Event.start_at >= monday, Event.start_at < sunday_end
    ).count()

    # Group-by type
    type_rows = (
        apply_read_filter(db, db.query(Event.event_type, func.count(Event.id)), operator, tenant_org_id)
        .group_by(Event.event_type)
        .all()
    )
    by_type = {t: n for t, n in type_rows}

    # Group-by status (nur Events mit metadata.status — meist Urlaub)
    status_rows = (
        apply_read_filter(
            db,
            db.query(Event.metadata_["status"].astext, func.count(Event.id)),
            operator,
            tenant_org_id,
        )
        .filter(Event.metadata_.has_key("status"))  # noqa: W601
        .group_by(Event.metadata_["status"].astext)
        .all()
    )
    by_status = {s: n for s, n in status_rows if s}

    return {
        "total": total,
        "today": today,
        "this_week": this_week,
        "by_type": by_type,
        "by_status": by_status,
    }


def compute_today_summary(
    db: Session, tenant_org_id: str, operator: Operator
) -> dict[str, Any]:
    """TodaySummary — Provider-Quelle für Heim-Karte 'Heute'."""
    tz = _tenant_tz(db, tenant_org_id)
    now = datetime.now(tz=tz)
    today_start = datetime.combine(now.date(), time(0, 0), tzinfo=tz)
    today_end = today_start + timedelta(days=1)

    base = apply_read_filter(db, db.query(Event), operator, tenant_org_id)

    event_count_today = base.filter(
        Event.start_at >= today_start, Event.start_at < today_end
    ).count()

    # Staff heute "im Haus" = aktive Staff − Staff mit Urlaub/Abwesenheit heute
    all_staff_count = (
        db.query(Person)
        .filter(
            Person.tenant_org_id == tenant_org_id,
            Person.kind == "staff",
            Person.active.is_(True),
            Person.deleted_at.is_(None),
        )
        .count()
    )

    # Wer hat heute Urlaub/Abwesenheit? participants @> [staff_person_id]
    out_today_rows = (
        db.query(Event.participants)
        .filter(
            Event.tenant_org_id == tenant_org_id,
            Event.deleted_at.is_(None),
            Event.event_type.in_(("urlaub", "abwesenheit")),
            Event.start_at < today_end,
            or_(Event.end_at.is_(None), Event.end_at >= today_start),
        )
        .all()
    )
    out_today_ids: set[int] = set()
    for (parts,) in out_today_rows:
        if isinstance(parts, list):
            out_today_ids.update(parts)

    staff_count_today = max(0, all_staff_count - len(out_today_ids))

    # Next event ab jetzt
    next_event = (
        apply_read_filter(db, db.query(Event), operator, tenant_org_id)
        .filter(Event.start_at >= now)
        .order_by(Event.start_at.asc())
        .first()
    )

    return {
        "event_count_today": event_count_today,
        "staff_count_today": staff_count_today,
        "next_event": next_event,
    }


# ---------------------------------------------------------- Resolver


def resolve_target_tenant(operator: Operator, payload_tenant: str | None) -> str | None:
    """Welcher Tenant ist gemeint?

    - Normaler Operator: aus operator.org_id
    - Developer: aus payload (sonst kein Tenant-Kontext)
    """
    if _is_developer(operator):
        return payload_tenant or operator.org_id
    return operator.org_id


def participants_resolved(
    db: Session, participant_ids: list[int]
) -> list[dict[str, Any]]:
    """Lädt Mini-Stempel für jede Person-ID — für UI-Avatare im Detail-View."""
    if not participant_ids:
        return []
    persons = (
        db.query(Person)
        .filter(Person.id.in_(participant_ids), Person.deleted_at.is_(None))
        .all()
    )
    return [
        {
            "id": p.id,
            "given_name": p.given_name,
            "family_name": p.family_name,
            "kind": p.kind,
        }
        for p in persons
    ]
