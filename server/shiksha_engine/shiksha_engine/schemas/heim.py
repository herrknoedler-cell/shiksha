"""Heim-Pydantic-Schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HeimCard(BaseModel):
    """Eine fertig gerenderte Karte für das Heim-Frontend."""
    id:         str
    title:      str
    subtitle:   str | None = None
    icon:       str | None = None
    action_url: str
    category:   str | None = None
    priority:   int = 5


class HeimResponse(BaseModel):
    greeting: str
    role:     str
    tenant:   str | None = None
    cards:    list[HeimCard]


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
