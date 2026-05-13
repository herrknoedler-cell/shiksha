"""Person-Pydantic-Schemas — Request/Response für CRUD."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from ..models.person import PERSON_KINDS


# ===================================================================
# Output (Detail + List-Item)
# ===================================================================

class PersonOut(BaseModel):
    id:            int
    legacy_id:     int | None = None
    legacy_source: str | None = None

    tenant_org_id: str
    kind:          str

    given_name:    str
    family_name:   str | None = None
    birth_date:    date | None = None
    gender:        str | None = None

    email:         str | None = None
    phone:         str | None = None
    address:       str | None = None

    group_id:      int | None = None
    entry_date:    date | None = None
    exit_date:     date | None = None

    notes:         str | None = None
    # SQLAlchemy belegt 'metadata' am Base — Model nutzt deshalb 'metadata_' als
    # Python-Attribut bei DB-Spalte 'metadata'. Pydantic liest via validation_alias.
    metadata:      dict = Field(default_factory=dict, validation_alias="metadata_")

    operator_id:   str | None = None
    active:        bool = True

    created_at:    datetime
    updated_at:    datetime
    deleted_at:    datetime | None = None

    @property
    def display_name(self) -> str:
        return f"{self.given_name} {self.family_name or ''}".strip()

    model_config = {"from_attributes": True, "populate_by_name": True}


class PersonListItem(BaseModel):
    """Schlankere Variante für Listen-Views."""
    id:           int
    kind:         str
    given_name:   str
    family_name:  str | None
    birth_date:   date | None
    group_id:     int | None
    active:       bool

    model_config = {"from_attributes": True}


# ===================================================================
# Input (Create / Update)
# ===================================================================

class PersonCreate(BaseModel):
    kind:         str
    given_name:   str = Field(min_length=1, max_length=128)
    family_name:  str | None = Field(default=None, max_length=128)
    birth_date:   date | None = None
    gender:       str | None = Field(default=None, max_length=8)

    email:        str | None = None
    phone:        str | None = Field(default=None, max_length=64)
    address:      str | None = None

    group_id:     int | None = None
    entry_date:   date | None = None
    exit_date:    date | None = None

    notes:        str | None = None
    metadata:     dict = Field(default_factory=dict)

    operator_id:  str | None = None
    active:       bool = True

    @field_validator("kind")
    @classmethod
    def _kind_must_be_valid(cls, v: str) -> str:
        if v not in PERSON_KINDS:
            raise ValueError(f"kind must be one of {PERSON_KINDS}, got '{v}'")
        return v


class PersonPatch(BaseModel):
    """Alle Felder optional. Nur gesetzte werden aktualisiert."""
    given_name:   str | None = Field(default=None, min_length=1, max_length=128)
    family_name:  str | None = Field(default=None, max_length=128)
    birth_date:   date | None = None
    gender:       str | None = Field(default=None, max_length=8)

    email:        str | None = None
    phone:        str | None = Field(default=None, max_length=64)
    address:      str | None = None

    group_id:     int | None = None
    entry_date:   date | None = None
    exit_date:    date | None = None

    notes:        str | None = None
    metadata:     dict | None = None

    operator_id:  str | None = None
    active:       bool | None = None


# ===================================================================
# Stats — Heim-Karten und Übersicht
# ===================================================================

class PersonStats(BaseModel):
    """Zusammenfassung pro Kind über alle aktiven Personen."""
    total:            int
    kind_count:       int  # Kinder
    staff_count:      int  # Mitarbeiter
    eltern_count:     int
    teilnehmer_count: int
    inactive_count:   int  # active=False, deleted_at IS NULL
