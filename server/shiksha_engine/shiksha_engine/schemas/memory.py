"""Memory-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class MemoryEntryOut(BaseModel):
    id: int
    operator_id: str
    edition: str
    text: str
    source_session_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    source_session_id: str | None = None
    # Optional: developer kann für anderen Operator schreiben
    operator_id: str | None = None


class MemoryPatchRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
