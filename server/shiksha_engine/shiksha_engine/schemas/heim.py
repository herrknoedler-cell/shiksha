"""Heim-Pydantic-Schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HeimCard(BaseModel):
    """Eine fertig gerenderte Karte für das Heim-Frontend."""
    id:          str
    title:       str
    subtitle:    str | None = None
    icon:        str | None = None
    action_url:  str
    category:    str | None = None
    priority:    int = 5
    # Konzept-Felder (5.5.6.6.a Pre-Sale, lebendig seit T-013):
    size:        str | None = None
    holi_border: str | None = None


# ---------------------------------------------------------- 5.5.D.5 Pages


class HeimPageCard(BaseModel):
    """Eine Karte in einer Heim-Page (mit Position + Size im 4×6-Grid).

    Spec: docs/specs/SHIKSHA_HEIM_LAYOUT_SPEC.md §2 + §4.
    """
    type:     str
    size:     str = "1x1"
    position: list[int]                       # [col, row], 0-basiert

    # Vom Loader gefüllt — kommt entweder aus Provider oder aus dem
    # Karten-Pool (heim_cards) wenn der type dort als id existiert.
    title:    str | None = None
    subtitle: str | None = None
    icon:     str | None = None
    url:      str | None = None
    accent:   str | None = None               # nur für action_*-Tiles
    data:     dict[str, Any] | None = None    # raw Provider-Output
    placeholder: bool = False                 # True wenn kein Provider/Pool-Match


class HeimPage(BaseModel):
    page_id: str
    label:   str
    cards:   list[HeimPageCard]


class HeimResponse(BaseModel):
    greeting: str
    role:     str
    tenant:   str | None = None
    # cards = deprecated flat-Liste (Backward-Compat für v1.0-Frontends).
    cards:    list[HeimCard]
    # pages   = neue 4×6-Grid-Struktur (5.5.D.5). Leer wenn heim_layouts[role]
    #           in der edition-yaml nicht definiert ist — dann nutzt das
    #           Frontend cards als Fallback.
    pages:    list[HeimPage] = Field(default_factory=list)
    schema_version: int = 1


class HeimConfigPatch(BaseModel):
    enabled:         bool | None = None
    custom_title:    str | None = Field(default=None, max_length=128)
    custom_subtitle: str | None = Field(default=None, max_length=255)
    extra_config:    dict | None = None


class HeimConfigOut(BaseModel):
    org_id:          str
    role:            str
    card_id:         str
    enabled:         bool
    custom_title:    str | None
    custom_subtitle: str | None
    extra_config:    dict | None

    model_config = {"from_attributes": True}
