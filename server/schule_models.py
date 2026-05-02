"""
SHIKSHA · SCHULE.EDITION · Pydantic Models V1
Stand: 25.04.2026
Wird von schule_orchestrator.py importiert.

Architektur-Prinzipien:
- Pydantic für Validierung, nicht ORM (DB läuft via SQLAlchemy in database.py)
- review_required = True per Default (V4-Prinzip 11)
- Confidence ist immer optional, aber wenn gesetzt → in Sprache sichtbar (V4-Prinzip 14)
- Sprache entsteht im Orchestrator, nie im Model (V4-Prinzip 3)
"""

from datetime import date, datetime
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# 1. Enums (als Literal für JSON-friendly Serialization)
# ---------------------------------------------------------------------------

SchoolType = Literal["yoga", "surf", "ski", "dance", "riding", "climbing", "other"]
EnrollmentStatus = Literal["inquiry", "pending_consent", "confirmed", "cancelled", "waitlist"]
ConsentStatus = Literal["all_valid", "consent_partial", "consent_pending", "consent_missing"]
CourseStatus = Literal["planned", "enrollment_open", "running", "completed", "cancelled", "on_demand"]
SessionStatus = Literal["scheduled", "running", "completed", "weather_postponed", "cancelled"]
PackageStatus = Literal["active", "paused", "consumed", "expired", "refunded"]
WeatherDecision = Literal["go", "no_go", "postpone", "pending"]
SignalSeverity = Literal["high", "mid", "low", "info"]
LanguageMode = Literal["flow", "action", "alert"]


# ---------------------------------------------------------------------------
# 2. Stammdaten-Modelle
# ---------------------------------------------------------------------------

class Address(BaseModel):
    street: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: str = "AT"


class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    web: Optional[str] = None


class BankAccount(BaseModel):
    iban: str
    bic: Optional[str] = None
    bank: Optional[str] = None
    holder: Optional[str] = None


class License(BaseModel):
    type: str
    level: Optional[str] = None
    valid_until: Optional[date] = None
    issued_by: Optional[str] = None


class ConsentRecord(BaseModel):
    type: str  # 'kursteilnahme', 'fotoeinverständnis', 'datenweitergabe', etc.
    by: str    # guardian_id oder student_id
    date: date
    valid_until: Optional[date] = None
    document_id: Optional[str] = None  # Link zum Foto/PDF im document.module


class Room(BaseModel):
    id: str
    name: str
    capacity: int
    size_qm: Optional[int] = None
    features: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. Schule (Entity)
# ---------------------------------------------------------------------------

class WeatherThresholds(BaseModel):
    wind_max_knots_beginner: int = 25
    wind_max_knots_advanced: int = 35
    wave_min_height_meters: float = 0.4
    wave_max_height_meters_beginner: float = 1.2
    decision_window_hours_before: int = 18


class School(BaseModel):
    id: str
    name: str
    edition: str = "schule.shiksha"
    type: SchoolType
    primary_address: Optional[Address] = None
    secondary_locations: list[dict] = Field(default_factory=list)
    contact: Optional[ContactInfo] = None
    uid_number: Optional[str] = None
    reg_number: Optional[str] = None
    tax_number: Optional[str] = None
    bank_account: Optional[BankAccount] = None
    business_hours: Optional[dict] = None
    weather_dependent: bool = False
    has_minors: bool = False
    insurance_info: Optional[dict] = None
    weather_thresholds: Optional[WeatherThresholds] = None
    rooms: list[Room] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 4. Personen
# ---------------------------------------------------------------------------

class Guardian(BaseModel):
    id: str
    full_name: str
    contact: Optional[ContactInfo] = None
    related_students: list[str] = Field(default_factory=list)
    consent_history: list[dict] = Field(default_factory=list)


class Student(BaseModel):
    id: str
    school_id: str
    full_name: str
    birthdate: Optional[date] = None
    is_minor: bool = False  # wird in DB als generated column gepflegt
    guardian_ids: list[str] = Field(default_factory=list)
    contact: Optional[ContactInfo] = None
    language: str = "de"
    level: dict[str, str] = Field(default_factory=dict)
    consent_records: list[ConsentRecord] = Field(default_factory=list)
    medical_notes: Optional[str] = None
    wetsuit_size: Optional[str] = None
    first_visit: Optional[date] = None
    metadata: dict = Field(default_factory=dict)


class Instructor(BaseModel):
    id: str
    school_id: str
    full_name: str
    role: Optional[str] = None
    contact: Optional[ContactInfo] = None
    languages: list[str] = Field(default_factory=lambda: ["de"])
    licenses: list[License] = Field(default_factory=list)
    background_check: Optional[dict] = None
    specialties: list[str] = Field(default_factory=list)
    availability: Optional[dict] = None
    hourly_rate: Optional[float] = None
    since: Optional[date] = None
    metadata: dict = Field(default_factory=dict)

    def has_valid_license_for(self, license_type: str, on_date: Optional[date] = None) -> bool:
        """Returns True if instructor holds a valid (non-expired) license matching license_type."""
        check_date = on_date or date.today()
        for lic in self.licenses:
            if lic.type.lower() == license_type.lower():
                if lic.valid_until is None or lic.valid_until >= check_date:
                    return True
        return False


# ---------------------------------------------------------------------------
# 5. Kurse & Sessions
# ---------------------------------------------------------------------------

class Course(BaseModel):
    id: str
    school_id: str
    name: str
    type: str
    level: Optional[str] = None
    capacity_min: int = 1
    capacity_max: int = 99
    price: Optional[float] = None
    currency: str = "EUR"
    duration_minutes: Optional[int] = None
    weather_dependent: bool = False
    status: CourseStatus = "planned"
    schedule_pattern: Optional[str] = None
    instructor_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    metadata: dict = Field(default_factory=dict)


class CourseSession(BaseModel):
    id: str
    course_id: str
    scheduled_at: datetime
    location: Optional[dict] = None
    instructor_id: Optional[str] = None
    status: SessionStatus = "scheduled"
    postponement_reason: Optional[str] = None
    rescheduled_to: Optional[datetime] = None
    expected_attendees: list[str] = Field(default_factory=list)
    actual_attendance: dict = Field(default_factory=dict)
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# 6. Anmeldung
# ---------------------------------------------------------------------------

class Enrollment(BaseModel):
    id: str
    student_id: str
    course_id: str
    status: EnrollmentStatus = "inquiry"
    consent_status: Optional[ConsentStatus] = None
    medical_clearance: Optional[dict] = None
    trial_class_session_id: Optional[str] = None
    enrolled_at: datetime = Field(default_factory=datetime.now)
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# 7. Pakete
# ---------------------------------------------------------------------------

class PackageTemplate(BaseModel):
    id: str
    school_id: str
    name: str
    count: int  # -1 = unlimited
    price: float
    currency: str = "EUR"
    validity_days: int
    applicable_course_types: list[str] = Field(default_factory=lambda: ["all"])
    metadata: dict = Field(default_factory=dict)


class PackageInstance(BaseModel):
    id: str
    template_id: str
    student_id: str
    remaining_count: int
    purchased_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime
    status: PackageStatus = "active"
    purchase_document_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class PackageConsumption(BaseModel):
    id: str
    package_instance_id: str
    course_session_id: Optional[str] = None
    consumed_at: datetime = Field(default_factory=datetime.now)
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# 8. Wetter
# ---------------------------------------------------------------------------

class WeatherForecast(BaseModel):
    wind_kn: Optional[float] = None
    wind_dir: Optional[str] = None
    wave_m: Optional[float] = None
    tide: Optional[str] = None
    temperature_c: Optional[float] = None
    source: str = "Open-Meteo"


class WeatherWindow(BaseModel):
    id: str
    course_session_id: str
    forecast_data: Optional[WeatherForecast] = None
    decision_required_at: Optional[datetime] = None
    decision: WeatherDecision = "pending"
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    alternative_plan: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# 9. Equipment
# ---------------------------------------------------------------------------

class Equipment(BaseModel):
    id: str
    school_id: str
    type: str
    model: Optional[str] = None
    size: Optional[str] = None
    status: Literal["available", "in_use", "damaged", "retired"] = "available"
    loaned_to_student_id: Optional[str] = None
    loaned_to_session_id: Optional[str] = None
    loaned_until: Optional[datetime] = None
    purchased_at: Optional[date] = None
    damage_note: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 10. Signale & State (analog ClubState aus CLUB.EDITION)
# ---------------------------------------------------------------------------

class SchuleSignal(BaseModel):
    id: Optional[int] = None
    school_id: Optional[str] = None
    signal_key: str
    severity: SignalSeverity = "info"
    params: dict = Field(default_factory=dict)
    related_entities: dict = Field(default_factory=dict)
    status: Literal["open", "acknowledged", "resolved", "ignored"] = "open"
    created_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None


class LanguageOutput(BaseModel):
    """Sprachausgabe: text_key + params (V4-Prinzip 4) — niemals direkter String."""
    mode: LanguageMode = "flow"
    text_key: str
    params: dict = Field(default_factory=dict)
    priority: Literal["low", "medium", "high"] = "medium"


class Pattern(BaseModel):
    pattern_key: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    related_signals: list[str] = Field(default_factory=list)
    seen_count: int = 1
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


class Action(BaseModel):
    """Vorschlag, nie Ausführung — review_required immer True in V1."""
    action_key: str
    title: str
    description: Optional[str] = None
    affected_entities: list[str] = Field(default_factory=list)
    review_required: bool = True
    estimated_impact: Optional[str] = None
    language: Optional[LanguageOutput] = None


class SchoolState(BaseModel):
    """Analog ClubState — Sprachfähige Zusammenfassung des Schul-Zustands."""
    school_id: str
    summary: str  # 1-2 Sätze in natürlicher Sprache
    patterns: list[Pattern] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    recommended_focus: list[Action] = Field(default_factory=list)
    recent_signals: list[SchuleSignal] = Field(default_factory=list)
    pattern_count: int = 0
    signal_count: int = 0
    as_of: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# 11. Request/Response Wrapper für API-Endpoints
# ---------------------------------------------------------------------------

class OrchestrateRequest(BaseModel):
    school_id: str
    focus: Optional[Literal["overview", "today", "alerts", "retention", "finance", "weather"]] = "overview"
    include_patterns: bool = True
    include_recommendations: bool = True


class OrchestrateResponse(BaseModel):
    school_state: SchoolState
    review_required: bool = True
    language: LanguageOutput


class CourseCreateRequest(BaseModel):
    school_id: str
    name: str
    type: str
    level: Optional[str] = None
    capacity_min: int = 1
    capacity_max: int = 99
    price: Optional[float] = None
    duration_minutes: Optional[int] = None
    weather_dependent: bool = False
    schedule_pattern: Optional[str] = None
    instructor_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class EnrollmentCreateRequest(BaseModel):
    student_id: str
    course_id: str
    package_instance_id: Optional[str] = None
    notes: Optional[str] = None


class WeatherDecisionRequest(BaseModel):
    weather_window_id: str
    decision: WeatherDecision
    decided_by: str  # instructor_id
    alternative_plan: Optional[str] = None
    notify_students: bool = False  # bleibt False — review_required


# ---------------------------------------------------------------------------
# 12. Module-Konfiguration
# ---------------------------------------------------------------------------

# pyright: reportInvalidTypeForm=false
SCHULE_EDITION_PROFILE: dict[str, Any] = {
    "edition": "schule.shiksha",
    "version": "1.0.0",
    "lead_domain": "education",
    "supporting_domains": ["scheduling", "weather", "communications", "payments", "safeguarding"],
    "modules_reused": [
        "people", "activity", "resource", "participation", "safeguarding",
        "competency", "assessment", "knowledge", "partnership", "funding",
        "document", "accounting", "calendar"
    ],
    "modules_new": [
        "course", "enrollment", "package", "instructor_qualification", "weather_dependency"
    ],
    "policies": [
        {"key": "schule.no_auto_certification", "level": "block", "scope": "Gate 3"},
        {"key": "schule.no_auto_minor_communication", "level": "block", "scope": "Gate 3"},
        {"key": "schule.consent_required_for_minors", "level": "block", "scope": "Gate 1"},
        {"key": "schule.weather_advisory_only", "level": "warn", "scope": "Gate 2"},
        {"key": "schule.instructor_license_check", "level": "warn", "scope": "Gate 2"},
    ],
    "review_required_default": True,
}


__all__ = [
    "SchoolType", "EnrollmentStatus", "ConsentStatus", "CourseStatus", "SessionStatus",
    "PackageStatus", "WeatherDecision", "SignalSeverity", "LanguageMode",
    "Address", "ContactInfo", "BankAccount", "License", "ConsentRecord", "Room",
    "WeatherThresholds", "School", "Guardian", "Student", "Instructor",
    "Course", "CourseSession", "Enrollment",
    "PackageTemplate", "PackageInstance", "PackageConsumption",
    "WeatherForecast", "WeatherWindow", "Equipment",
    "SchuleSignal", "LanguageOutput", "Pattern", "Action", "SchoolState",
    "OrchestrateRequest", "OrchestrateResponse",
    "CourseCreateRequest", "EnrollmentCreateRequest", "WeatherDecisionRequest",
    "SCHULE_EDITION_PROFILE",
]
