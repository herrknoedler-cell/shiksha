"""AuditLog — wer hat wann was geändert."""

from datetime import datetime

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ._base import Base, now_col, schema_args


class AuditLog(Base):
    """Wird von der Audit-Middleware automatisch geschrieben für Mutations."""

    __tablename__ = "audit_logs"
    __table_args__ = schema_args()

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id:    Mapped[str|None] = mapped_column(String(64), nullable=True, index=True)
    actor_role:  Mapped[str|None] = mapped_column(String(32), nullable=True)
    action:      Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # z.B. "persona_edit", "memory_create", "memory_delete", "operator_create"
    target_type: Mapped[str|None] = mapped_column(String(32), nullable=True)
    target_id:   Mapped[str|None] = mapped_column(String(64), nullable=True)
    diff:        Mapped[dict|None] = mapped_column(JSON, nullable=True)
    request_path: Mapped[str|None] = mapped_column(String(255), nullable=True)
    request_method: Mapped[str|None] = mapped_column(String(8), nullable=True)
    ip_address:  Mapped[str|None] = mapped_column(String(45), nullable=True)
    ts:          Mapped[datetime] = now_col()

    def __repr__(self) -> str:
        return f"<AuditLog #{self.id} {self.actor_id} {self.action} {self.target_type}>"
