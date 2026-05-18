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
from ..schemas.heim import HeimCard, HeimPage, HeimPageCard, HeimResponse
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

    # ---- Pages (5.5.D.5) ----
    # Wenn editions/<edition>.yaml ein heim_layouts.<role> definiert,
    # bauen wir die strukturierte Page-Liste. Sonst pages=[] und das
    # Frontend nutzt die flache cards-Liste.
    pages = _build_heim_pages(
        operator=operator,
        db=db,
        edition_cfg=cfg or {},
        core_cfg=core_cfg or {},
        card_pool=raw_cards,
    )

    return HeimResponse(
        greeting=greeting,
        role=operator.role,
        tenant=operator.org_id,
        cards=rendered,
        pages=pages,
        schema_version=1,
    )


# ===================================================================
# Pages-Builder (5.5.D.5)
# Spec: docs/specs/SHIKSHA_HEIM_LAYOUT_SPEC.md
# ===================================================================


def _build_heim_pages(
    *,
    operator: Operator,
    db: DBSession,
    edition_cfg: dict,
    core_cfg: dict,
    card_pool: list[dict],
) -> list[HeimPage]:
    """Baut die Pages-Liste für die Rolle des Operators.

    Sucht in edition-yaml und core-yaml nach heim_layouts.<role>.
    Edition gewinnt über core (Edition-Override-Pattern).

    Für jede Karte: versucht Provider via type-string, fällt zurück
    auf card_pool-Lookup (heim_cards mit id == type), sonst Placeholder.
    """
    layouts_edition = (edition_cfg.get("heim_layouts") or {})
    layouts_core    = (core_cfg.get("heim_layouts") or {})

    role_layout = layouts_edition.get(operator.role)
    if role_layout is None:
        role_layout = layouts_core.get(operator.role)
    if not role_layout:
        return []

    # Card-Pool als Dict für schnellen Lookup
    pool_by_id = {c["id"]: c for c in card_pool if c.get("id")}

    pages: list[HeimPage] = []
    for page_def in role_layout:
        cards: list[HeimPageCard] = []
        for card_def in page_def.get("cards", []):
            cards.append(
                _build_page_card(
                    card_def=card_def,
                    operator=operator,
                    db=db,
                    pool_by_id=pool_by_id,
                )
            )
        pages.append(HeimPage(
            page_id=page_def["page_id"],
            label=page_def.get("label", page_def["page_id"]),
            cards=cards,
        ))
    return pages


def _build_page_card(
    *,
    card_def: dict,
    operator: Operator,
    db: DBSession,
    pool_by_id: dict[str, dict],
) -> HeimPageCard:
    """Eine einzelne Page-Karte bauen.

    Resolution-Reihenfolge:
      1. action_* → Tile-Button mit Inline-Properties aus dem Layout (title,
         icon, accent, url) — kein Provider-Lookup
      2. type == 'dayclock' → Komponente, kein Provider
      3. type in pool_by_id → nutze Pool-Eintrag (title, icon, action_url,
         data_provider) plus optional Provider-Call
      4. sonst → Placeholder-Tile
    """
    type_str = card_def["type"]
    size = card_def.get("size", "1x1")
    position = card_def.get("position", [0, 0])

    # Action-Tile
    if type_str.startswith("action_"):
        return HeimPageCard(
            type=type_str,
            size=size,
            position=position,
            title=card_def.get("title"),
            icon=card_def.get("icon"),
            url=card_def.get("url"),
            accent=card_def.get("accent", "warm"),
            placeholder=False,
        )

    # Dayclock-Komponente
    if type_str == "dayclock":
        return HeimPageCard(
            type=type_str,
            size=size,
            position=position,
            title="Tages-Uhr",
            placeholder=False,
        )

    # Pool-Lookup
    pool_entry = pool_by_id.get(type_str)
    if pool_entry is None:
        return HeimPageCard(
            type=type_str,
            size=size,
            position=position,
            title=type_str,
            subtitle="Karte noch nicht implementiert",
            placeholder=True,
        )

    # Provider-Call (falls vorhanden)
    provider_name = pool_entry.get("data_provider")
    data: dict[str, Any] = {}
    subtitle = pool_entry.get("subtitle_template") or pool_entry.get("subtitle")
    if provider_name:
        try:
            data = call_provider(provider_name, operator, db) or {}
            if data.get("visible") is False:
                # Auch placeholder-mäßig anzeigen, damit Grid-Layout stabil bleibt
                return HeimPageCard(
                    type=type_str,
                    size=size,
                    position=position,
                    title=pool_entry.get("title", type_str),
                    subtitle="—",
                    icon=pool_entry.get("icon"),
                    url=pool_entry.get("action_url"),
                    placeholder=False,
                )
            if subtitle:
                subtitle = render_subtitle(subtitle, data)
        except Exception:
            log.exception("Page-card provider %s raised", provider_name)
            subtitle = "—"

    return HeimPageCard(
        type=type_str,
        size=size,
        position=position,
        title=pool_entry.get("title", type_str),
        subtitle=subtitle,
        icon=pool_entry.get("icon"),
        url=pool_entry.get("action_url"),
        data=data or None,
        placeholder=False,
    )
