"""
SHIKSHA · CAMPING.EDITION · Pydantic Models V1
Stand: 25.04.2026

Architektur-Prinzipien (gleich wie SCHULE):
- review_required = True per Default
- Confidence in Sprache, nicht Prozent
- Sprache entsteht im Orchestrator
- text_key + params, nie String

Camping-spezifisch:
- Cross-edition safeguarding-Integration via SafeguardingSignalRef
- Polarity ('positiv'/'neutral'/'negativ') zusätzlich zu severity
"""

from datetime import date, datetime
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Enums
# ---------------------------------------------------------------------------

CampsiteType = Literal["family + glamping", "outdoor + dauer­camper", "family", "glamping_only", "stellplatz"]
PitchCategory = Literal["komfort", "standard", "naturplatz", "service", "dauer­camper", "glamping", "premium_inntal", "outdoor_naturplatz", "hundewiesen­zone"]
ReservationStatus = Literal["inquiry", "pending_payment", "confirmed", "cancelled", "no_show"]
StayStatus = Literal["running", "completed", "cancelled_during"]
SignalSeverity = Literal["high", "mid", "low", "info"]
SignalPolarity = Literal["positiv", "neutral", "negativ"]
LanguageMode = Literal["flow", "action", "alert"]
ServiceType = Literal["breakfast", "wash", "sauna", "rental_bike", "rental_boat", "kiosk"]
JourneyStage = Literal["inquiry", "booked", "pre_stay", "arrival", "stay", "departure", "post_stay"]


# ---------------------------------------------------------------------------
# 2. Stammdaten-Modelle
# ---------------------------------------------------------------------------

class Address(BaseModel):
    street: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: str = "DE"
    region: Optional[str] = None


class ContactInfo(BaseModel):
    geschaeftsfuehrer: Optional[str] = None
    co_inhaber: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    web: Optional[str] = None


class BankAccount(BaseModel):
    iban: str
    bic: Optional[str] = None
    bank: Optional[str] = None
    holder: Optional[str] = None


# ---------------------------------------------------------------------------
# 3. Campsite (Entity)
# ---------------------------------------------------------------------------

class Campsite(BaseModel):
    id: str
    name: str
    edition: str = "camping.shiksha"
    type: Optional[CampsiteType] = None
    primary_address: Optional[Address] = None
    contact: Optional[ContactInfo] = None
    uid_number: Optional[str] = None
    tax_number: Optional[str] = None
    reg_number: Optional[str] = None
    bank_account: Optional[BankAccount] = None
    season: Optional[dict] = None
    capacities: Optional[dict] = None
    infrastructure: list[str] = Field(default_factory=list)
    weather_dependent: bool = True
    has_minors: bool = False
    has_pool: bool = False
    has_playground: bool = False
    dog_friendly: bool = False
    languages_supported: list[str] = Field(default_factory=lambda: ["de"])
    insurance_info: Optional[dict] = None
    behoerden_auflagen: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 4. Pitch / Accommodation
# ---------------------------------------------------------------------------

class Pitch(BaseModel):
    id: str
    campsite_id: str
    label: str
    category: PitchCategory
    size_m2: Optional[int] = None
    electricity_amp: int = 0
    water: bool = False
    drain: bool = False
    shadow: Optional[Literal["voll", "halb", "kein"]] = None
    dog_allowed: bool = False
    view: Optional[str] = None
    status: Literal["available", "occupied", "maintenance", "blocked"] = "available"
    metadata: dict = Field(default_factory=dict)


class Accommodation(BaseModel):
    id: str
    campsite_id: str
    type: Literal["mobile_home", "glamping_tent", "cabin"]
    name: Optional[str] = None
    size_m2: Optional[int] = None
    beds: Optional[int] = None
    amenities: list[str] = Field(default_factory=list)
    weekly_high: Optional[float] = None
    weekly_low: Optional[float] = None
    dog_allowed: bool = False
    status: str = "available"
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 5. Personen
# ---------------------------------------------------------------------------

class GuardianCamping(BaseModel):
    id: str
    full_name: str
    contact: Optional[dict] = None
    related_minors: list[str] = Field(default_factory=list)
    consent_history: list[dict] = Field(default_factory=list)


class Guest(BaseModel):
    id: str
    campsite_id: Optional[str] = None
    full_name: str
    primary_adult: Optional[str] = None
    address: Optional[Address] = None
    contact: Optional[dict] = None
    language: str = "de"
    vehicle_plate: Optional[str] = None
    is_minor: bool = False
    birthdate: Optional[date] = None
    guardian_ids: list[str] = Field(default_factory=list)
    first_visit: Optional[date] = None
    visit_count: int = 0
    last_visit: Optional[date] = None
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 6. Reservation / Stay
# ---------------------------------------------------------------------------

class Reservation(BaseModel):
    id: str
    campsite_id: str
    guest_id: str
    pitch_id: Optional[str] = None
    accommodation_id: Optional[str] = None
    from_date: date
    to_date: date
    persons: int = 1
    minors_count: int = 0
    status: ReservationStatus = "inquiry"
    deposit_paid: bool = False
    deposit_due: Optional[date] = None
    total_amount: Optional[float] = None
    type: str = "standard"  # 'standard' | 'saisonpacht'
    cancellation_record: Optional[dict] = None
    metadata: dict = Field(default_factory=dict)


class Stay(BaseModel):
    id: str
    reservation_id: Optional[str] = None
    campsite_id: str
    guest_id: str
    pitch_id: Optional[str] = None
    accommodation_id: Optional[str] = None
    check_in: date
    check_out: Optional[date] = None
    persons: int = 1
    minors_count: int = 0
    dog: Optional[str] = None
    status: StayStatus = "running"
    notes: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class Meldeschein(BaseModel):
    id: str
    stay_id: str
    person_data: dict
    signed_at: Optional[datetime] = None
    signed_by: Optional[str] = None
    document_id: Optional[str] = None
    retention_until: Optional[date] = None
    anonymized_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# 7. Pricing
# ---------------------------------------------------------------------------

class PricingPeriod(BaseModel):
    id: str
    campsite_id: str
    label: str
    from_date_pattern: Optional[str] = None
    to_date_pattern: Optional[str] = None
    factor: float = 1.0


class PricingRule(BaseModel):
    id: str
    campsite_id: str
    pitch_category: Optional[str] = None
    rule_key: str
    base_price_eur: float
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 8. Utility Metering
# ---------------------------------------------------------------------------

class Meter(BaseModel):
    id: str
    campsite_id: str
    pitch_id: Optional[str] = None
    accommodation_id: Optional[str] = None
    type: Literal["electricity", "water"]
    serial: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class UtilityReading(BaseModel):
    id: str
    meter_id: str
    reading_value: float
    unit: str = "kWh"
    read_at: datetime = Field(default_factory=datetime.now)
    read_by: Optional[str] = None
    document_id: Optional[str] = None  # Foto-Beleg
    consumption_since_previous: Optional[float] = None
    expected_consumption: Optional[float] = None
    anomaly_flag: bool = False
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# 9. Services + Guest Requests
# ---------------------------------------------------------------------------

class Service(BaseModel):
    id: str
    campsite_id: str
    name: str
    type: ServiceType
    base_price_eur: float
    bookable_in_advance: bool = True
    metadata: dict = Field(default_factory=dict)


class ServiceConsumption(BaseModel):
    id: str
    service_id: str
    stay_id: Optional[str] = None
    guest_id: Optional[str] = None
    consumed_at: datetime = Field(default_factory=datetime.now)
    quantity: int = 1
    total_eur: Optional[float] = None
    notes: Optional[str] = None


class GuestRequest(BaseModel):
    id: str
    campsite_id: str
    stay_id: Optional[str] = None
    guest_id: Optional[str] = None
    request_type: Literal["question", "complaint", "service", "incident"]
    subject: Optional[str] = None
    body: Optional[str] = None
    severity: SignalSeverity = "low"
    status: Literal["open", "in_progress", "resolved", "closed"] = "open"
    received_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    document_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 10. Journey
# ---------------------------------------------------------------------------

class JourneyEvent(BaseModel):
    id: Optional[int] = None
    campsite_id: str
    guest_id: Optional[str] = None
    stay_id: Optional[str] = None
    stage: JourneyStage
    event_key: str
    event_data: dict = Field(default_factory=dict)
    triggered_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# 11. Signale, Patterns, State (Camping)
# ---------------------------------------------------------------------------

class CampingSignal(BaseModel):
    id: Optional[int] = None
    campsite_id: Optional[str] = None
    signal_key: str
    severity: SignalSeverity = "info"
    polarity: SignalPolarity = "neutral"
    params: dict = Field(default_factory=dict)
    related_entities: dict = Field(default_factory=dict)
    status: Literal["open", "acknowledged", "resolved", "ignored"] = "open"
    created_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None


class LanguageOutput(BaseModel):
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
    polarity: SignalPolarity = "neutral"


class Action(BaseModel):
    action_key: str
    title: str
    description: Optional[str] = None
    affected_entities: list[str] = Field(default_factory=list)
    review_required: bool = True
    estimated_impact: Optional[str] = None
    language: Optional[LanguageOutput] = None


class CampState(BaseModel):
    campsite_id: str
    summary: str
    patterns: list[Pattern] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    recommended_focus: list[Action] = Field(default_factory=list)
    recent_signals: list[CampingSignal] = Field(default_factory=list)
    pattern_count: int = 0
    signal_count: int = 0
    occupancy_pct: Optional[float] = None
    as_of: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# 12. Cross-Edition Safeguarding Reference
# ---------------------------------------------------------------------------

class SafeguardingSignalRef(BaseModel):
    """Verweis aufs Safeguarding-Modul, damit CAMPING-Orchestrator es konsumieren kann."""
    signal_key: str           # 'safeguarding.pool_inspection_due', 'safeguarding.aufsicht_lueckig', etc.
    severity_camping: SignalSeverity  # CAMPING-Edition kann severity erhöhen (Pool > Yoga-Mattenraum)
    source_module: str = "safeguarding"
    cross_edition: bool = True


# ---------------------------------------------------------------------------
# 13. Request/Response Wrapper
# ---------------------------------------------------------------------------

class CampingOrchestrateRequest(BaseModel):
    campsite_id: str
    focus: Optional[Literal["overview", "today", "alerts", "occupancy", "supplier", "weather", "safeguarding"]] = "overview"
    include_patterns: bool = True
    include_recommendations: bool = True


class CampingOrchestrateResponse(BaseModel):
    camp_state: CampState
    review_required: bool = True
    language: LanguageOutput


class ReservationCreateRequest(BaseModel):
    campsite_id: str
    guest_id: str
    pitch_id: Optional[str] = None
    accommodation_id: Optional[str] = None
    from_date: date
    to_date: date
    persons: int = 1
    minors_count: int = 0
    dog: Optional[str] = None


class CheckInRequest(BaseModel):
    reservation_id: str
    actual_persons: int
    actual_minors: int = 0
    dog: Optional[str] = None
    document_id_meldeschein: Optional[str] = None


class UtilityReadingCreateRequest(BaseModel):
    meter_id: str
    reading_value: float
    unit: str = "kWh"
    document_id: Optional[str] = None  # Foto-Beleg


# ---------------------------------------------------------------------------
# 14. Edition-Profile
# ---------------------------------------------------------------------------

CAMPING_EDITION_PROFILE: dict[str, Any] = {
    "edition": "camping.shiksha",
    "version": "1.0.0",
    "lead_domain": "hospitality",
    "supporting_domains": ["scheduling", "weather", "communications", "payments", "safeguarding", "operations"],
    "modules_reused": [
        "people", "resource", "partnership", "community", "accounting",
        "document", "calendar", "safeguarding", "assessment", "access"
    ],
    "modules_new": [
        "pitch", "reservation", "check_in_out", "seasonal_pricing", "utility_metering", "guest_journey"
    ],
    "policies": [
        {"key": "camping.no_auto_rebooking", "level": "block", "scope": "Gate 3"},
        {"key": "camping.guest_data_minimal", "level": "warn", "scope": "Gate 4"},
        {"key": "camping.minor_supervision_required", "level": "warn", "scope": "Gate 1"},
        {"key": "camping.weather_advisory_only", "level": "warn", "scope": "Gate 2"},
        {"key": "camping.utility_overage_alert", "level": "warn", "scope": "Gate 2"},
        {"key": "camping.no_auto_review_request", "level": "block", "scope": "Gate 3"},
    ],
    "review_required_default": True,
}


__all__ = [
    "CampsiteType", "PitchCategory", "ReservationStatus", "StayStatus", "SignalSeverity",
    "SignalPolarity", "LanguageMode", "ServiceType", "JourneyStage",
    "Address", "ContactInfo", "BankAccount", "Campsite", "Pitch", "Accommodation",
    "GuardianCamping", "Guest", "Reservation", "Stay", "Meldeschein",
    "PricingPeriod", "PricingRule", "Meter", "UtilityReading",
    "Service", "ServiceConsumption", "GuestRequest", "JourneyEvent",
    "CampingSignal", "LanguageOutput", "Pattern", "Action", "CampState",
    "SafeguardingSignalRef",
    "CampingOrchestrateRequest", "CampingOrchestrateResponse",
    "ReservationCreateRequest", "CheckInRequest", "UtilityReadingCreateRequest",
    "CAMPING_EDITION_PROFILE",
]
