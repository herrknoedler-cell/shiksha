"""Auth-related Pydantic schemas."""

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class RegistrationStartRequest(BaseModel):
    """Optional: für Setup-Token-Flow."""
    setup_token: str | None = None


class RegistrationStartResponse(BaseModel):
    """JSON dass die navigator.credentials.create() bekommt."""
    options: dict[str, Any]
    operator_id: str


class RegistrationFinishRequest(BaseModel):
    operator_id: str
    credential: dict[str, Any]  # Response von navigator.credentials.create()


class AuthenticationStartRequest(BaseModel):
    operator_id: str


class AuthenticationStartResponse(BaseModel):
    options: dict[str, Any]


class AuthenticationFinishRequest(BaseModel):
    operator_id: str
    credential: dict[str, Any]  # Response von navigator.credentials.get()


class TokenResponse(BaseModel):
    token: str
    role: str
    edition: str
    operator_id: str
    display_name: str


class MeResponse(BaseModel):
    operator_id: str
    display_name: str
    role: str
    edition: str
    org_id: str | None
    org_name: str | None
    email: EmailStr | None


class EmailOtpRequest(BaseModel):
    """Notausgang — Phase 2, jetzt Platzhalter."""
    email: EmailStr
