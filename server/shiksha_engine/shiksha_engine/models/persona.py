"""PersonaPrompt — system prompts pro Persona + Edition, mit Versionierung."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import schema_name
from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    pass


class PersonaPrompt(Base):
    """System-Prompt für eine bestimmte Persona (z.B. tagesausklang)
    in einer bestimmten Edition (kita|camping|...|*).

    edition="*" = cross-edition Default.
    Höchste version pro (name, edition) wird genutzt.
    """

    __tablename__ = "persona_prompts"
    __table_args__ = schema_args()

    name:         Mapped[str] = mapped_column(String(64), primary_key=True)
    edition:      Mapped[str] = mapped_column(String(32), primary_key=True, default="*")
    version:      Mapped[int] = mapped_column(Integer,    primary_key=True, default=1)

    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    description:   Mapped[str|None] = mapped_column(Text, nullable=True)

    updated_by:   Mapped[str|None] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.operators.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at:   Mapped[datetime] = now_col()

    def __repr__(self) -> str:
        return f"<PersonaPrompt {self.name}@{self.edition} v{self.version}>"
