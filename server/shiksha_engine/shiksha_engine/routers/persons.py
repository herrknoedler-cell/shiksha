"""Persons-Router — CRUD über Stammdaten (Kinder, Mitarbeiter, ...).

Spec: PHASE_1_5_SPEC.md §6.1.

Endpoints:
  GET    /api/v1/persons?kind=kind&q=Anna&active_only=true
  GET    /api/v1/persons/stats                       — Aggregat-Stats
  GET    /api/v1/persons/{id}                        — Detail
  POST   /api/v1/persons                             — Anlegen
  PATCH  /api/v1/persons/{id}                        — Bearbeiten
  DELETE /api/v1/persons/{id}                        — Soft-Delete

Auth:
  GET-Endpoints: staff-Rollen (leitung, padagoge, trainer, operator) + developer
  Mutationen:    nur leitung + developer
  Klienten (eltern, teilnehmer): kein Zugriff in Phase 1.5

Tenant-Isolation: alle Queries automatisch auf operator.org_id gefiltert.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DBSession

from ..db import get_db
from ..deps import (
    get_current_operator,
    require_leitung_or_developer,
    require_operator_or_developer,
)
from ..models import Operator, Person
from ..schemas.person import (
    PersonCreate,
    PersonListItem,
    PersonOut,
    PersonPatch,
    PersonStats,
)

router = APIRouter()


# ===================================================================
# Helpers
# ===================================================================

def _scope_query(query, operator: Operator):
    """Tenant-Isolation. Developer ohne org_id sieht alles (Debug-Modus)."""
    if operator.kind == "system":  # developer
        return query  # Developer kann alle Tenants sehen
    if not operator.org_id:
        # Staff ohne Tenant — gibt es eigentlich nicht, aber defensiv
        return query.where(Person.tenant_org_id == "__none__")
    return query.where(Person.tenant_org_id == operator.org_id)


def _ensure_same_tenant_or_developer(person: Person, operator: Operator):
    if operator.kind == "system":
        return
    if person.tenant_org_id != operator.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")


# ===================================================================
# GET — Liste mit Filter
# ===================================================================

@router.get(
    "",
    response_model=list[PersonListItem],
    operation_id="persons_list",
)
def list_persons(
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_operator_or_developer)],
    kind: str | None = Query(
        None,
        description="Filter nach kind (kind, staff, eltern, teilnehmer, gast, trainer)",
    ),
    q: str | None = Query(
        None,
        description="Volltext-Suche in given_name, family_name",
    ),
    active_only: bool = Query(True),
    include_deleted: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[PersonListItem]:
    """Liste der Personen im Tenant, optional gefiltert."""
    query = select(Person)
    query = _scope_query(query, operator)

    if kind:
        query = query.where(Person.kind == kind)
    if active_only:
        query = query.where(Person.active.is_(True))
    if not include_deleted:
        query = query.where(Person.deleted_at.is_(None))
    if q:
        pattern = f"%{q}%"
        query = query.where(or_(
            Person.given_name.ilike(pattern),
            Person.family_name.ilike(pattern),
        ))

    query = (
        query
        .order_by(Person.kind, Person.given_name, Person.family_name)
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(query).scalars().all()
    return [PersonListItem.model_validate(r) for r in rows]


# ===================================================================
# GET /stats — Übersicht
# ===================================================================

@router.get(
    "/stats",
    response_model=PersonStats,
    operation_id="persons_stats",
)
def persons_stats(
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_operator_or_developer)],
) -> PersonStats:
    """Aggregat-Statistiken für Heim-Karten und Übersicht."""
    base = select(func.count(Person.id))
    base = _scope_query(base, operator)
    base = base.where(Person.deleted_at.is_(None))

    def _count_where(*conditions) -> int:
        q = base
        for cond in conditions:
            q = q.where(cond)
        return db.execute(q).scalar_one() or 0

    total = _count_where()

    return PersonStats(
        total            = total,
        kind_count       = _count_where(Person.kind == "kind", Person.active.is_(True)),
        staff_count      = _count_where(Person.kind == "staff", Person.active.is_(True)),
        eltern_count     = _count_where(Person.kind == "eltern", Person.active.is_(True)),
        teilnehmer_count = _count_where(Person.kind == "teilnehmer", Person.active.is_(True)),
        inactive_count   = _count_where(Person.active.is_(False)),
    )


# ===================================================================
# GET /{id} — Detail
# ===================================================================

@router.get(
    "/{person_id}",
    response_model=PersonOut,
    operation_id="persons_detail",
)
def get_person(
    person_id: int,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_operator_or_developer)],
) -> PersonOut:
    person = db.get(Person, person_id)
    if person is None or person.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Person not found")
    _ensure_same_tenant_or_developer(person, operator)
    return PersonOut.model_validate(person)


# ===================================================================
# POST — Anlegen
# ===================================================================

@router.post(
    "",
    response_model=PersonOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="persons_create",
)
def create_person(
    payload: PersonCreate,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_leitung_or_developer)],
) -> PersonOut:
    """Eine neue Person anlegen. Tenant = Tenant des Operators."""
    if not operator.org_id and operator.kind != "system":
        raise HTTPException(
            status_code=400,
            detail="Operator has no org_id — cannot create person",
        )

    # Developer ohne org_id muss org_id explizit setzen — über metadata.tenant_org_id
    # Für Phase 1.5 reicht: nimm operator.org_id, sonst raise.
    target_tenant = operator.org_id
    if not target_tenant:
        raise HTTPException(
            status_code=400,
            detail="Developer must call from a tenant context (org_id required)",
        )

    person = Person(
        tenant_org_id = target_tenant,
        kind          = payload.kind,
        given_name    = payload.given_name.strip(),
        family_name   = (payload.family_name or "").strip() or None,
        birth_date    = payload.birth_date,
        gender        = payload.gender,
        email         = payload.email,
        phone         = payload.phone,
        address       = payload.address,
        group_id      = payload.group_id,
        entry_date    = payload.entry_date,
        exit_date     = payload.exit_date,
        notes         = payload.notes,
        metadata_     = payload.metadata or {},
        operator_id   = payload.operator_id,
        active        = payload.active,
    )
    db.add(person)
    db.flush()
    return PersonOut.model_validate(person)


# ===================================================================
# PATCH — Bearbeiten
# ===================================================================

@router.patch(
    "/{person_id}",
    response_model=PersonOut,
    operation_id="persons_patch",
)
def patch_person(
    person_id: int,
    payload: PersonPatch,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_leitung_or_developer)],
) -> PersonOut:
    person = db.get(Person, person_id)
    if person is None or person.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Person not found")
    _ensure_same_tenant_or_developer(person, operator)

    # Nur Felder updaten, die übergeben wurden (auch explizite None überschreiben
    # wir nicht — Pydantic-model_dump(exclude_unset=True) trennt sauber).
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field == "given_name" and value is not None:
            value = value.strip()
        elif field == "family_name" and value is not None:
            value = value.strip() or None
        # SQLAlchemy-Naming-Kollision: Python-Attribut ist metadata_, DB-Spalte metadata.
        attr = "metadata_" if field == "metadata" else field
        setattr(person, attr, value)

    person.updated_at = datetime.now(timezone.utc)
    db.add(person)
    db.flush()
    return PersonOut.model_validate(person)


# ===================================================================
# DELETE — Soft-Delete
# ===================================================================

@router.delete(
    "/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="persons_delete",
)
def delete_person(
    person_id: int,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_leitung_or_developer)],
) -> None:
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    _ensure_same_tenant_or_developer(person, operator)

    if person.deleted_at is None:
        person.deleted_at = datetime.now(timezone.utc)
        person.active     = False
        db.add(person)
        db.flush()
