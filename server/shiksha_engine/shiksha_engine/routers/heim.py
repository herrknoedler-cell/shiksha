"""Heim-Router — /api/v1/heim und /api/v1/heim/config.

Spec: SHIKSHA_HEIM_SPEC.md §9, §6.2.

Drei Endpoints:
  GET    /api/v1/heim                          — Karten-Liste für aktiven Operator
  GET    /api/v1/heim/config?role=X            — Karten-Pool für Rolle (Leitungs-View)
  PATCH  /api/v1/heim/config/{role}/{card_id}  — Karte für Rolle anpassen
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ..db import get_db
from ..deps import (
    get_current_operator,
    require_authenticated,
    require_leitung_or_developer,
)
from ..models import Operator, TenantHeimConfig
from ..models.operator import STAFF_ROLES, KLIENT_ROLES, SYSTEM_ROLES, LEGACY_ROLES
from ..schemas.heim import (
    HeimCard,
    HeimConfigOut,
    HeimConfigPatch,
    HeimResponse,
)
from ..services.edition_config import get_edition_config
from ..services.heim_loader import load_heim

router = APIRouter()


ALL_VALID_ROLES = STAFF_ROLES + KLIENT_ROLES + SYSTEM_ROLES + LEGACY_ROLES


# ===================================================================
# Hauptseite — die Karten-Liste für den aktiven Operator
# ===================================================================

@router.get("", response_model=HeimResponse, operation_id="heim_get")
def get_heim(
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_authenticated)],
) -> HeimResponse:
    """Fertige Karten-Liste für den eingeloggten Operator."""
    return load_heim(operator, db)


# ===================================================================
# Konfig-Read — Leitung sieht den Karten-Pool für eine Rolle
# ===================================================================

@router.get(
    "/config",
    response_model=list[dict],
    operation_id="heim_config_list",
)
def list_heim_config(
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_leitung_or_developer)],
    role: str = Query(..., description="Welche Rolle wollen wir sehen?"),
) -> list[dict]:
    """Liefert pro Karte: Default-Definition + aktuell aktivierter Status.

    Antwort:
        [{
          "card_id": "anwesenheit_today",
          "title": "Anwesenheit heute",
          "icon": "presence",
          "category": "core",
          "default_enabled": true,
          "is_overridden": false,
          "enabled": true,
          "custom_title": null,
          "custom_subtitle": null
        }, ...]
    """
    if role not in ALL_VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role}")

    # Karten-Pool für Operator-Edition laden
    cfg = get_edition_config(operator.edition) or {}
    cards: list[dict] = list(cfg.get("heim_cards") or [])
    core_cfg = get_edition_config("core") or {}
    cards = list(core_cfg.get("heim_cards") or []) + cards

    # Karten filtern nach role_scope
    candidates = [
        c for c in cards
        if not c.get("role_scope") or role in c.get("role_scope", [])
    ]

    # Bestehende Overrides nachlesen
    overrides = {}
    if operator.org_id:
        rows = db.execute(
            select(TenantHeimConfig)
            .where(TenantHeimConfig.org_id == operator.org_id)
            .where(TenantHeimConfig.role == role)
        ).scalars().all()
        overrides = {r.card_id: r for r in rows}

    result = []
    for card in candidates:
        cid = card["id"]
        ov = overrides.get(cid)
        result.append({
            "card_id":         cid,
            "title":           card.get("title"),
            "icon":            card.get("icon"),
            "category":        card.get("category"),
            "default_enabled": True,
            "is_overridden":   ov is not None,
            "enabled":         ov.enabled if ov else True,
            "custom_title":    ov.custom_title if ov else None,
            "custom_subtitle": ov.custom_subtitle if ov else None,
            "extra_config":    ov.extra_config if ov else None,
        })
    return result


# ===================================================================
# Konfig-Patch — Leitung passt eine Karte an
# ===================================================================

@router.patch(
    "/config/{role}/{card_id}",
    response_model=HeimConfigOut,
    operation_id="heim_config_patch",
)
def patch_heim_config(
    role: str,
    card_id: str,
    payload: HeimConfigPatch,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_leitung_or_developer)],
) -> HeimConfigOut:
    """Aktiviert/deaktiviert oder überschreibt Texte einer Karte für eine Rolle."""

    if role not in ALL_VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role}")

    if not operator.org_id:
        raise HTTPException(
            status_code=400,
            detail="Operator has no org_id — cannot configure tenant heim",
        )

    # Karten-ID gegen den Pool prüfen, damit niemand zufällige IDs anlegt
    cfg = get_edition_config(operator.edition) or {}
    core_cfg = get_edition_config("core") or {}
    valid_ids = {
        c["id"] for c in (core_cfg.get("heim_cards") or []) + (cfg.get("heim_cards") or [])
    }
    if card_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Card '{card_id}' not in pool")

    # Existing Override?
    existing = db.get(TenantHeimConfig, (operator.org_id, role, card_id))
    if existing is None:
        existing = TenantHeimConfig(
            org_id=operator.org_id,
            role=role,
            card_id=card_id,
        )
        db.add(existing)

    # Updates anwenden (nur Felder die übergeben wurden)
    if payload.enabled is not None:
        existing.enabled = payload.enabled
    if payload.custom_title is not None:
        existing.custom_title = payload.custom_title.strip() or None
    if payload.custom_subtitle is not None:
        existing.custom_subtitle = payload.custom_subtitle.strip() or None
    if payload.extra_config is not None:
        existing.extra_config = payload.extra_config

    existing.updated_by = operator.id
    existing.updated_at = datetime.now(timezone.utc)
    db.flush()

    return HeimConfigOut.model_validate(existing)
