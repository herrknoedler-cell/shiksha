"""TenantHeimConfig — pro-(org, role, card)-Override für Heim-Karten.

Spec: SHIKSHA_HEIM_SPEC.md §6.2.

Wenn ein Eintrag existiert: er überschreibt den Default aus
editions/<edition>.yaml. Wenn nicht: Default gilt.

Beispiel: Mira deaktiviert die Speiseplan-Karte für Eltern in Krummelus →
  org_id='krummelus', role='eltern', card_id='speiseplan', enabled=false
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import schema_name
from ._base import Base, now_col, schema_args


class TenantHeimConfig(Base):
    __tablename__ = "tenant_heim_config"
    __table_args__ = schema_args()

    org_id:          Mapped[str] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role:            Mapped[str] = mapped_column(String(32), primary_key=True)
    card_id:         Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled:         Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    custom_title:    Mapped[str|None] = mapped_column(String(128), nullable=True)
    custom_subtitle: Mapped[str|None] = mapped_column(String(255), nullable=True)
    extra_config:    Mapped[dict|None] = mapped_column(JSON, nullable=True)
    updated_by:      Mapped[str|None] = mapped_column(String(64), nullable=True)
    updated_at:      Mapped[datetime] = now_col()

    def __repr__(self) -> str:
        state = "on" if self.enabled else "off"
        return f"<HeimConfig {self.org_id}/{self.role}/{self.card_id} {state}>"
