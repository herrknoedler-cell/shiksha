"""
SHIKSHA · document.module V2 — Erweiterungen
Stand: 25.04.2026

Erweitert document.module V1.2 (V4) um neue Dokumenttypen,
die für SCHULE und CAMPING relevant sind. Validiert gegen die 20
KI-generierten fiktiven Dokumente in den Edition-Fixtures.

V1.2 hatte:
    invoice, dunning, penalty_notice, offer, contract, note, unknown

V2 ergänzt:
    delivery_note          — Lieferschein (Bäcker, Schreiner, ION, Yogashop)
    enrollment_form        — Anmeldebogen (Yoga, Surf, Camping)
    medical_clearance      — Hebammen-/Arzt-Bescheinigung
    meter_reading          — Strom-/Wasser-Ablesung mit Foto-Beleg
    behoerden_bescheid     — Behörden-Post (Gesundheitsamt, Gemeinde, Tourismus)
    weather_postponement   — Wetter-Verschiebungs-Email an Gruppe
    guest_complaint        — Gäste-Beschwerde / Anfrage / Meldung
    reservation_confirmation — Reservierungs-Bestätigung an Gast
    service_consumption    — Brötchen-Bestellung, Wäsche, Sauna

Architektur:
- Neue Pydantic-Models extending the V1.2 Document
- Field-Vokabular pro Typ
- Classifier-Hints (typische Keywords) für Klassifikation
- Cross-Edition-Tags (welche Edition konsumiert welchen Typ)
"""

from datetime import date, datetime
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Erweiterung des DocumentType-Vokabulars (extends V1.2)
# ---------------------------------------------------------------------------

DocumentType = Literal[
    # V1.2 (bestehend)
    "invoice", "dunning", "penalty_notice", "offer", "contract", "note", "unknown",
    # V2 (neu)
    "delivery_note",
    "enrollment_form",
    "medical_clearance",
    "meter_reading",
    "behoerden_bescheid",
    "weather_postponement",
    "guest_complaint",
    "reservation_confirmation",
    "service_consumption",
]


# ---------------------------------------------------------------------------
# 2. Neue Field-Schemas pro Dokumenttyp
# ---------------------------------------------------------------------------

class DeliveryNoteFields(BaseModel):
    """Lieferschein — Bäcker, Schreiner, Großhändler."""
    supplier_name: Optional[str] = None
    delivery_date: Optional[date] = None
    delivery_time: Optional[str] = None  # "06:35"
    delivery_note_number: Optional[str] = None
    items: list[dict] = Field(default_factory=list)  # [{pos, article, quantity, unit}]
    total_amount: Optional[float] = None
    currency: str = "EUR"
    recipient_name: Optional[str] = None
    delivery_address: Optional[dict] = None
    signed_off: bool = False
    confidence_note: Optional[str] = None


class EnrollmentFormFields(BaseModel):
    """Anmeldebogen — Yoga-/Surf-/Tanz-/Reit-Schule."""
    school_name: Optional[str] = None
    student_name: Optional[str] = None
    student_birthdate: Optional[date] = None
    is_minor: bool = False
    guardian_name: Optional[str] = None
    guardian_contact: Optional[dict] = None  # phone, email
    course_selected: Optional[str] = None
    package_selected: Optional[str] = None
    package_price: Optional[float] = None
    consents: list[dict] = Field(default_factory=list)  # [{type, granted, valid_until}]
    medical_notes: Optional[str] = None
    signature_present: bool = False
    signed_at_location: Optional[str] = None
    signed_at_date: Optional[date] = None
    confidence_note: Optional[str] = None


class MedicalClearanceFields(BaseModel):
    """Hebammen-/Arzt-Bescheinigung."""
    issuer_name: Optional[str] = None
    issuer_role: Optional[str] = None  # "Hebamme", "Arzt"
    issuer_credential_id: Optional[str] = None  # ÖHV-Nr., Arzt-Nr.
    patient_name: Optional[str] = None
    patient_birthdate: Optional[date] = None
    clearance_for: Optional[str] = None  # "Pre-Natal Yoga", "Surfen", "Skifahren"
    valid_until: Optional[date] = None
    medical_notes_for_instructor: Optional[str] = None
    signed_at_date: Optional[date] = None
    confidence_note: Optional[str] = None


class MeterReadingFields(BaseModel):
    """Strom-/Wasser-Ablesung mit Foto-Beleg."""
    meter_type: Literal["electricity", "water", "gas"] = "electricity"
    pitch_or_unit_id: Optional[str] = None
    reading_value: Optional[float] = None
    reading_unit: str = "kWh"
    reading_date: Optional[date] = None
    reading_time: Optional[str] = None
    previous_reading_value: Optional[float] = None
    previous_reading_date: Optional[date] = None
    consumption_since_previous: Optional[float] = None
    expected_consumption: Optional[float] = None
    anomaly_flag: bool = False
    anomaly_reason: Optional[str] = None
    photo_id: Optional[str] = None  # FK zu Foto im Document-System
    notes: Optional[str] = None
    confidence_note: Optional[str] = None


class BehoerdenBescheidFields(BaseModel):
    """Behördenpost — Gemeinde, Gesundheitsamt, Tourismus, Gewerbeaufsicht."""
    authority_name: Optional[str] = None
    authority_address: Optional[dict] = None
    case_number: Optional[str] = None  # "OA-Sylt/2026-Surfschulen/0034"
    document_type_authority: Optional[str] = None  # "Bescheid", "Erinnerung", "Inspektionsbericht"
    addressee_name: Optional[str] = None
    document_date: Optional[date] = None
    deadline: Optional[date] = None
    auflagen: list[str] = Field(default_factory=list)
    referenced_law: list[str] = Field(default_factory=list)
    fees: Optional[float] = None
    fees_due_date: Optional[date] = None
    iban_for_payment: Optional[str] = None
    requires_response: bool = False
    confidence_note: Optional[str] = None


class WeatherPostponementFields(BaseModel):
    """Wetter-Verschiebungs-Email an betroffene Gäste/Schüler."""
    sender_name: Optional[str] = None
    sender_organization: Optional[str] = None
    sent_at: Optional[datetime] = None
    affected_session_date: Optional[date] = None
    affected_session_name: Optional[str] = None
    new_session_date: Optional[date] = None
    weather_reason: Optional[str] = None  # "Wind 38 kn"
    affected_recipients_count: Optional[int] = None
    plan_b_offered: Optional[str] = None
    confidence_note: Optional[str] = None


class GuestComplaintFields(BaseModel):
    """Gäste-Beschwerde, Anfrage, Beobachtung."""
    guest_name: Optional[str] = None
    guest_pitch_or_room: Optional[str] = None
    received_at: Optional[datetime] = None
    received_via: Optional[str] = None  # "App", "Email", "persönlich"
    complaint_target: Optional[str] = None  # was wird beanstandet
    severity_self_reported: Optional[Literal["low", "mid", "high"]] = None
    body_text: Optional[str] = None
    operator_resolution_proposal: Optional[str] = None
    confidence_note: Optional[str] = None


class ReservationConfirmationFields(BaseModel):
    """Reservierungs-Bestätigung — Camping oder Schule."""
    organization_name: Optional[str] = None
    reservation_number: Optional[str] = None
    confirmed_at: Optional[date] = None
    customer_name: Optional[str] = None
    customer_address: Optional[dict] = None
    pitch_or_resource: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    nights: Optional[int] = None
    persons: Optional[int] = None
    minors_count: Optional[int] = None
    deposit_amount: Optional[float] = None
    deposit_paid: bool = False
    total_amount: Optional[float] = None
    currency: str = "EUR"
    notes_for_arrival: Optional[str] = None
    confidence_note: Optional[str] = None


class ServiceConsumptionFields(BaseModel):
    """Service-Bestellung — Brötchen, Wäsche, Sauna."""
    organization_name: Optional[str] = None
    customer_name: Optional[str] = None
    customer_pitch_or_room: Optional[str] = None
    service_type: Optional[str] = None
    quantity: Optional[int] = None
    requested_for_date: Optional[date] = None
    total_eur: Optional[float] = None
    confidence_note: Optional[str] = None


# ---------------------------------------------------------------------------
# 3. Classifier-Hints (Keyword-Patterns für die initiale Klassifikation)
# ---------------------------------------------------------------------------

CLASSIFIER_HINTS_V2: dict[str, dict] = {
    "delivery_note": {
        "primary_keywords": ["lieferschein", "auslieferung", "lieferung an", "delivery note"],
        "supporting_keywords": ["pos", "menge", "stück", "lieferschein-nr", "versand"],
        "structural_hints": ["enthält Tabelle mit Pos./Art./Menge"],
        "negative_keywords": ["rechnung", "mahnung", "anmeldung"],
        "consumed_by": ["camping.shiksha", "schule.shiksha", "club.shiksha"],
    },
    "enrollment_form": {
        "primary_keywords": ["anmeldung", "anmeldebogen", "registration", "kursteilnahme"],
        "supporting_keywords": [
            "vor- und nachname", "geburtsdatum", "einverständnis",
            "erziehungsberechtigt", "guardian", "package", "paket"
        ],
        "structural_hints": ["enthält Checkboxen für Konsente"],
        "negative_keywords": ["lieferschein", "rechnung"],
        "consumed_by": ["schule.shiksha", "club.shiksha"],
    },
    "medical_clearance": {
        "primary_keywords": [
            "bescheinigung", "ärztliche", "hebammen", "freigabe",
            "medical clearance", "fitness for"
        ],
        "supporting_keywords": [
            "schwangerschaftswoche", "diagnose", "ohv", "öhv-mitgliedsnummer",
            "ärztin", "arzt", "patientin"
        ],
        "structural_hints": ["Stempel + Unterschrift erwartet"],
        "negative_keywords": ["lieferschein", "kursanmeldung"],
        "consumed_by": ["schule.shiksha", "camping.shiksha"],
    },
    "meter_reading": {
        "primary_keywords": ["zähler", "ablesung", "kwh", "verbrauch", "meter reading"],
        "supporting_keywords": ["pitch", "stellplatz", "vorherige ablesung", "differenz"],
        "structural_hints": ["enthält große Zähler-Zahl, idealerweise Foto-Bezug"],
        "negative_keywords": ["rechnung", "mahnung"],
        "consumed_by": ["camping.shiksha"],
    },
    "behoerden_bescheid": {
        "primary_keywords": [
            "bescheid", "aktenzeichen", "rechtsbehelfsbelehrung", "auflage",
            "ordnungsamt", "gesundheitsamt", "tourismus", "gemeinde"
        ],
        "supporting_keywords": [
            "fälligkeit", "frist", "nutzungsgebühr", "verwaltungsgebühr",
            "kurtaxe", "tourismusabgabe"
        ],
        "structural_hints": ["formelle Briefstruktur, oft Stempel"],
        "negative_keywords": ["lieferschein", "anmeldung"],
        "consumed_by": ["camping.shiksha", "schule.shiksha"],
    },
    "weather_postponement": {
        "primary_keywords": [
            "verschiebung", "wetter", "sturm", "verschoben",
            "weather postponement", "neuer termin"
        ],
        "supporting_keywords": [
            "wind", "kn", "wellen", "sicherheit", "plan b", "alternative"
        ],
        "structural_hints": ["E-Mail-Form, an Verteiler/Gruppe"],
        "negative_keywords": ["lieferschein", "rechnung"],
        "consumed_by": ["schule.shiksha", "camping.shiksha"],
    },
    "guest_complaint": {
        "primary_keywords": [
            "beschwerde", "complaint", "ich möchte mich beschweren",
            "stört uns", "could you", "would you mind"
        ],
        "supporting_keywords": [
            "nachbarpitch", "lärm", "ruhezeit", "hund", "kind", "pool"
        ],
        "structural_hints": ["informelle Email-/Nachrichtenstruktur"],
        "negative_keywords": ["bescheid", "lieferschein"],
        "consumed_by": ["camping.shiksha", "schule.shiksha"],
    },
    "reservation_confirmation": {
        "primary_keywords": [
            "reservierung", "bestätigung", "buchungs-bestätigung",
            "booking confirmation", "anreise", "abreise"
        ],
        "supporting_keywords": [
            "pitch", "anzahlung", "restzahlung", "personen",
            "von ... bis", "nächte"
        ],
        "structural_hints": ["enthält Datums-Tabelle, oft Anzahlung"],
        "negative_keywords": ["mahnung", "lieferschein"],
        "consumed_by": ["camping.shiksha", "schule.shiksha"],
    },
    "service_consumption": {
        "primary_keywords": ["bestellung", "service", "brötchen", "wäsche"],
        "supporting_keywords": ["pitch", "menge", "wunschdatum"],
        "structural_hints": ["kurz, oft App-/Formular-Eingabe"],
        "negative_keywords": ["rechnung", "anmeldung"],
        "consumed_by": ["camping.shiksha"],
    },
}


# ---------------------------------------------------------------------------
# 4. Test-Mapping: KI-Dokumente → erwarteter Typ
# ---------------------------------------------------------------------------

TEST_DOCUMENT_MAPPINGS: list[dict] = [
    # SCHULE
    {"file": "yoga_anmeldung_lukas_minor.md", "expected_type": "enrollment_form",
     "expected_minor": True, "expected_consents": ["kursteilnahme", "fotoeinverständnis"]},
    {"file": "yoga_rechnung_10er_karte.md", "expected_type": "invoice",
     "expected_amount": 180.00, "expected_iban_prefix": "AT"},
    {"file": "yoga_mahnung_monatskarte.md", "expected_type": "dunning",
     "expected_reminder_level": 1, "expected_amount_due": 115.00},
    {"file": "yoga_hebammen_bescheinigung.md", "expected_type": "medical_clearance",
     "expected_issuer_role": "Hebamme", "expected_clearance_for": "Pre-Natal Yoga"},
    {"file": "yoga_lieferschein_matten.md", "expected_type": "delivery_note",
     "expected_supplier_name": "Yogashop Berlin GmbH"},
    {"file": "yoga_versicherung_erstrechnung.md", "expected_type": "invoice",
     "expected_amount": 535.02, "expected_supplier_name": "Wiener Städtische"},

    # SURF
    {"file": "surf_anmeldung_5tage_english.md", "expected_type": "enrollment_form",
     "expected_language": "en", "expected_student_country": "IE"},
    {"file": "surf_wetter_verschiebung.md", "expected_type": "weather_postponement",
     "expected_weather_reason": "Wind 38 kn"},
    {"file": "surf_rechnung_privat_stunde.md", "expected_type": "invoice",
     "expected_amount": 110.00},
    {"file": "surf_lieferschein_wetsuits.md", "expected_type": "delivery_note",
     "expected_supplier_name": "ION"},
    {"file": "surf_versicherung_mahnung.md", "expected_type": "dunning",
     "expected_authority": "ARAG", "expected_amount_due": 1488.93},
    {"file": "surf_behoerde_strandzonen.md", "expected_type": "behoerden_bescheid",
     "expected_authority": "Gemeinde Sylt", "expected_fees": 1984.00},

    # CAMPING
    {"file": "camping_reservierung_bestaetigung.md", "expected_type": "reservation_confirmation",
     "expected_nights": 14, "expected_total": 1285.20},
    {"file": "camping_lieferschein_baecker.md", "expected_type": "delivery_note",
     "expected_supplier_name": "Bäckerei Lechner"},
    {"file": "camping_strom_ablesung.md", "expected_type": "meter_reading",
     "expected_reading_value": 247.3, "expected_anomaly": True},
    {"file": "camping_lieferschein_schreiner.md", "expected_type": "delivery_note",
     "expected_supplier_name": "Schreinerei Maria Brand"},
    {"file": "camping_kurtaxe_anschreiben.md", "expected_type": "behoerden_bescheid",
     "expected_authority": "Markt Berchtesgaden"},
    {"file": "camping_pool_inspektion.md", "expected_type": "behoerden_bescheid",
     "expected_authority": "Gesundheitsamt Berchtesgadener Land"},
    {"file": "camping_anfrage_email_solo.md", "expected_type": "guest_complaint",
     "expected_subtype": "question"},
    {"file": "camping_versicherung_beitrag.md", "expected_type": "invoice",
     "expected_amount": 2930.97, "expected_supplier_name": "Bayerische Versicherungskammer"},
    {"file": "camping_beschwerde_hund.md", "expected_type": "guest_complaint",
     "expected_subtype": "complaint"},
]


# ---------------------------------------------------------------------------
# 5. Hilfsfunktionen
# ---------------------------------------------------------------------------

def classify_document_v2(text: str, fallback_to_v1: bool = True) -> tuple[str, float, str]:
    """
    Klassifiziert Dokumenttext anhand der Keyword-Hints.
    Returns: (document_type, confidence, classification_reason)

    Wenn kein V2-Typ matcht, fällt auf V1.2-Klassifikation zurück (durch Caller),
    sonst 'unknown'.
    """
    text_lower = text.lower()
    scores: dict[str, float] = {}
    reasons: dict[str, list[str]] = {}

    for doc_type, hints in CLASSIFIER_HINTS_V2.items():
        score = 0.0
        matches = []

        for kw in hints["primary_keywords"]:
            if kw in text_lower:
                score += 1.0
                matches.append(f"primary:{kw}")

        for kw in hints.get("supporting_keywords", []):
            if kw in text_lower:
                score += 0.3
                matches.append(f"support:{kw}")

        for kw in hints.get("negative_keywords", []):
            if kw in text_lower:
                score -= 0.5
                matches.append(f"negative:{kw}")

        scores[doc_type] = score
        reasons[doc_type] = matches

    if not scores or max(scores.values()) <= 0:
        return ("unknown", 0.0, "no_keywords_matched")

    best = max(scores, key=lambda k: scores[k])
    raw_score = scores[best]

    # Confidence: pseudo-normalisiert auf 0-0.95
    confidence = min(0.4 + 0.15 * raw_score, 0.95)

    return (best, confidence, ", ".join(reasons[best][:5]))


def field_schema_for_type(doc_type: str) -> Optional[type]:
    """Returns the Pydantic-Field-Schema-Klasse für einen Dokumenttyp."""
    schemas: dict[str, type] = {
        "delivery_note": DeliveryNoteFields,
        "enrollment_form": EnrollmentFormFields,
        "medical_clearance": MedicalClearanceFields,
        "meter_reading": MeterReadingFields,
        "behoerden_bescheid": BehoerdenBescheidFields,
        "weather_postponement": WeatherPostponementFields,
        "guest_complaint": GuestComplaintFields,
        "reservation_confirmation": ReservationConfirmationFields,
        "service_consumption": ServiceConsumptionFields,
    }
    return schemas.get(doc_type)


# ---------------------------------------------------------------------------
# 6. Edition-Routing-Helper
# ---------------------------------------------------------------------------

def editions_consuming_type(doc_type: str) -> list[str]:
    """Returns die Editionen, die diesen Dokumenttyp interessant finden."""
    hints = CLASSIFIER_HINTS_V2.get(doc_type, {})
    return hints.get("consumed_by", [])


__all__ = [
    "DocumentType",
    "DeliveryNoteFields", "EnrollmentFormFields", "MedicalClearanceFields",
    "MeterReadingFields", "BehoerdenBescheidFields", "WeatherPostponementFields",
    "GuestComplaintFields", "ReservationConfirmationFields", "ServiceConsumptionFields",
    "CLASSIFIER_HINTS_V2",
    "TEST_DOCUMENT_MAPPINGS",
    "classify_document_v2",
    "field_schema_for_type",
    "editions_consuming_type",
]
