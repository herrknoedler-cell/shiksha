"""Chat-Request/Response-Schemas."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = Field(
        default=None,
        description="Wenn None: neue Session wird angelegt. Sonst: weiter mit bestehender.",
    )
    user_message: str = Field(min_length=1, max_length=8000)
    persona: str = Field(
        default="tagesausklang",
        description="Welche Persona angesprochen wird: tagesausklang | kennenlernen | ...",
    )


class ChatResponse(BaseModel):
    session_id: str
    shiksha_response: str
    mode: str | None = Field(
        default=None,
        description="PRÄSENZ | FOKUS | VERDICHTEN | AUSKLANG (heuristisch erkannt)",
    )
    tokens_used: int = 0
