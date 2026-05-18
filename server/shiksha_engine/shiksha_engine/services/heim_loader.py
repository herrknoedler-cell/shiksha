"""Heim-Card-Loader — baut die Karten-Liste für einen Operator.

Ablauf (Spec §12):
1. Karten-Pool aus editions/<edition>.yaml laden
2. Filtern nach edition_scope + role_scope
3. tenant_heim_config-Overrides anwenden
4. Daten-Provider aufrufen (intern, kein HTTP)
5. Visibility-Rules auswerten
6. Subtitle-Templates rendern
7. Nach time_priority sortieren
8. Greeting generieren

Output: HeimResponse-Schema.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ..models import Operator, TenantHeimConfig
from ..schemas.heim import HeimCard, HeimResponse
from .edition_config import get_edition_config
from .heim_providers import call_provider, evaluate_visibility, render_subtitle

log = logging.getLogger("shiksha.heim.loader")


# ===================================================================
# Greeting (Phase 1: nur tageszeit-basiert)
# ===================================================================

def _current_slot(hour: int) -> str:
    if 5 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 16:
        return "afternoon"
    if 17 <= hour <= 21:
        return "evening"
    return "night"


def _greeting_for(slot: str, display_name: str) -> str:
    name = display_name or ""
    name_part = f", {name}" if name else ""
    return {
        "morning":   f"Guten Morgen{name_part}.",
        "afternoon": f"Hallo{name_part}.",
        "evening":   f"Schönen Abend{name_part}.",
        "night":     f"Noch wach{name_part}?",
    }[slot]


# ===================================================================
# Card-Loader
# ===================================================================

def _card_matches_scope(card: dict, edition: str, role: str) -> bool:
    edition_scope = card.get("edition_scope", ["*"])
    role_scope    = card.get("role_scope", [])

    if "*" not in edition_scope and edition not in edition_scope:
        return False
    if role_scope and role not in role_scope:
        return False
    return True


def _load_config_overrides(
    db: DBSession,
    org_id: str | None,
    role: str,
) -> dict[str, TenantHeimConfig]:
    """Lädt die Heim-Overrides für (org_id, role). Key = card_id."""
    if not org_id:
        return {}
    rows = db.execute(
        select(TenantHeimConfig)
        .where(TenantHeimConfig.org_id == org_id)
        .where(TenantHeimConfig.role == role)
    ).scalars().all()
    return {r.card_id: r for r in rows}


def _normalize_priority(card: dict, slot: str) -> int:
    """Extrahiert die Sortier-Priorität für die aktuelle Tageszeit."""
    tp = card.get("time_priority") or {}
    return int(tp.get(slot, 5))


def _render_card(
    card_def: dict,
    override: TenantHeimConfig | None,
    operator: Operator,
    db: DBSession,
    slot: str,
) -> HeimCard | None:
    """Eine einzelne Karte fertig rendern. None wenn nicht sichtbar."""

    # Override-Aktiviert-Status prüfen
    if override and not override.enabled:
        return None

    # Daten-Provider rufen, falls vorhanden
    provider_name = card_def.get("data_provider")
    data: dict = {}
    if provider_name:
        data = call_provider(provider_name, operator, db)

    # Visibility-Rule auswerten
    rule = card_def.get("visibility_rule")
    if not evaluate_visibility(rule, data):
        return None

    # Titel + Subtitle mit Override-Texten oder Default
    default_title = card_def.get("title", card_def["id"])
    default_subtitle = card_def.get("subtitle_template")

    title = (override.custom_title if override and override.custom_title
             else default_title)

    subtitle_template = (override.custom_subtitle if override and override.custom_subtitle
                         else default_subtitle)
    subtitle = render_subtitle(subtitle_template, data)

    priority = _normalize_priority(card_def, slot)

    return HeimCard(
        id=card_def["id"],
        title=title,
        subtitle=subtitle,
        icon=card_def.get("icon"),
        action_url=card_def["action_url"],
        category=card_def.get("category"),
        priority=priority,
        size=card_def.get("size"),
        holi_border=card_def.get("holi_border"),
    )


def load_heim(operator: Operator, db: DBSession) -> HeimResponse:
    """Hauptfunktion — baut das Heim für einen Operator."""

    cfg = get_edition_config(operator.edition)
    raw_cards: list[dict] = (cfg or {}).get("heim_cards") or []

    # Cross-edition Karten: aus core.yaml laden, falls vorhanden, plus mergen.
    # Bewusst einfach: Cross-edition geht über edition_scope=["*"] in jeder
    # Edition-yaml ODER über ein separates core.yaml. Wir nehmen core.yaml.
    core_cfg = get_edition_config("core")
    if core_cfg and core_cfg.get("heim_cards"):
        raw_cards = list(core_cfg["heim_cards"]) + raw_cards

    slot = _current_slot(datetime.now().hour)
    overrides = _load_config_overrides(db, operator.org_id, operator.role)

    # Karten filtern + rendern
    rendered: list[HeimCard] = []
    seen_ids: set[str] = set()
    for card_def in raw_cards:
        card_id = card_def.get("id")
        if not card_id or card_id in seen_ids:
            continue
        seen_ids.add(card_id)

        if not _card_matches_scope(card_def, operator.edition, operator.role):
            continue

        rendered_card = _render_card(
            card_def, overrides.get(card_id), operator, db, slot
        )
        if rendered_card is not None:
            rendered.append(rendered_card)

    # Sortieren nach Priorität (1 = oben), dann nach ID alphabetisch
    rendered.sort(key=lambda c: (c.priority, c.id))

    greeting = _greeting_for(slot, operator.display_name)
    return HeimResponse(
        greeting=greeting,
        role=operator.role,
        tenant=operator.org_id,
        cards=rendered,
    )
