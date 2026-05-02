# compression.py
# SHIKSHA document.module — high_level_summary
# Version: 1.0
# Purpose: Komprimierter Modellkontext für Orchestrator und API.
#          NICHT für UI-Text — das ist formulator.py.
#
# Design-Prinzipien:
# - high_level_summary ergänzt v2, ersetzt es nicht
# - Satzbudget verbindlich: max 3 Sätze, Priorisierung definiert
# - recommended_focus: nur wenn handlungsrelevant — sonst leer
# - Confidence lebt in der Sprache, nie als Prozentzahl
# - Cold-Start ehrlich: lieber leer als halluziniert
# - Strikte Trennung zu formulator.py (dieser Modul = Modellkontext)

from typing import Optional, List
from pydantic import BaseModel

from document_models import DocumentAnalysisResponse, DocumentFieldCandidate


# ---------------------------------------------------------------------------
# OUTPUT MODEL
# ---------------------------------------------------------------------------

class DocumentSummary(BaseModel):
    """
    Komprimierter Modellkontext für einen analysierten Dokument.
    Bestimmt für Orchestrator-Input und API-Response — nicht für UI.
    """
    document_id: str
    document_type: str                      # erkannter Typ
    entity_name: Optional[str] = None      # vorgeschlagene Entity, falls confident genug
    entity_id: Optional[str] = None
    entity_confidence: str = "unknown"     # "high" | "medium" | "low" | "unknown"

    # Kernfelder — nur gefüllte, confidence-gewichtete Werte
    amount: Optional[str] = None           # Betrag mit Währung, falls extrahiert
    primary_date: Optional[str] = None     # fälligkeitsdatum > dokumentdatum > tatzeit
    reference: Optional[str] = None       # Rechnungsnr / Aktenzeichen / Referenz

    # Uncertainty
    has_open_decisions: bool = False       # mind. ein Feld ohne sicheren Wert
    uncertainty_types: List[str] = []     # "entity" | "amount" | "date" | "iban" | "type"

    # Fokus-Empfehlung — nur wenn handlungsrelevant
    recommended_focus: str = ""           # leer = kein Fokus nötig

    # Komprimierter Satz für Modellkontext (max 3 Sätze)
    high_level_summary: str = ""


# ---------------------------------------------------------------------------
# CONFIDENCE BUCKETING
# ---------------------------------------------------------------------------

def _bucket(confidence: float) -> str:
    """Wandelt float-Confidence in Sprachstufe um."""
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.45:
        return "medium"
    if confidence > 0.0:
        return "low"
    return "unknown"


# ---------------------------------------------------------------------------
# FIELD HELPERS
# ---------------------------------------------------------------------------

def _get_field(
    fields: List[DocumentFieldCandidate],
    key: str,
    min_confidence: float = 0.0,
) -> Optional[DocumentFieldCandidate]:
    """Gibt das erste Feld mit diesem key zurück, wenn confidence >= min_confidence."""
    for f in fields:
        if f.field_key == key and f.confidence >= min_confidence:
            return f
    return None


def _primary_date(
    fields: List[DocumentFieldCandidate],
    document_type: str,
) -> Optional[str]:
    """
    Priorisierung: due_date > document_date > invoice_date > incident_date.
    Gibt nur Werte mit confidence >= 0.50 zurück.
    """
    priority = {
        "invoice":        ["due_date", "invoice_date"],
        "dunning":        ["due_date", "document_date"],
        "penalty_notice": ["due_date", "incident_date", "document_date"],
        "offer":          ["valid_until", "offer_date"],
        "contract":       ["contract_date"],
        "note":           ["document_date"],
        "unknown":        ["due_date", "document_date"],
    }
    keys = priority.get(document_type, ["due_date", "document_date"])
    for key in keys:
        f = _get_field(fields, key, min_confidence=0.50)
        if f:
            return f.field_value
    return None


def _primary_reference(
    fields: List[DocumentFieldCandidate],
    document_type: str,
) -> Optional[str]:
    """
    Priorisierung: invoice_number > case_number > reference_number > offer_number.
    Confidence >= 0.60.
    """
    priority = {
        "invoice":        ["invoice_number"],
        "dunning":        ["referenced_invoice_number", "reference_number"],
        "penalty_notice": ["case_number"],
        "offer":          ["offer_number"],
        "contract":       ["reference_number"],
        "unknown":        ["reference_number", "invoice_number"],
    }
    keys = priority.get(document_type, ["reference_number"])
    for key in keys:
        f = _get_field(fields, key, min_confidence=0.60)
        if f:
            return f.field_value
    return None


def _amount_with_currency(
    fields: List[DocumentFieldCandidate],
    document_type: str,
) -> Optional[str]:
    """
    Gibt Betrag + Währung als formatierten String zurück.
    Nur wenn amount_confidence >= 0.55.
    """
    amount_keys = {
        "invoice":        "amount_total",
        "dunning":        "amount_due",
        "penalty_notice": "amount_due",
        "offer":          "amount_total",
        "unknown":        "amount_due",
    }
    amount_key = amount_keys.get(document_type, "amount_total")
    amount_field = _get_field(fields, amount_key, min_confidence=0.55)
    if not amount_field:
        return None

    currency_field = _get_field(fields, "currency", min_confidence=0.80)
    currency = currency_field.field_value if currency_field else "EUR"
    return f"{amount_field.field_value} {currency}"


# ---------------------------------------------------------------------------
# UNCERTAINTY DETECTION
# ---------------------------------------------------------------------------

def _detect_uncertainties(
    analysis: DocumentAnalysisResponse,
) -> List[str]:
    """
    Gibt Liste von Uncertainty-Typen zurück.
    Reproduzierbare Definitionen — nicht heuristisch.

    Typen:
    - "type"   → document_type == "unknown" ODER detection_debug runner_up_score >= best_score * 0.7
    - "entity" → entity_suggestion.confidence < 0.45 ODER suggested_entity_id is None
    - "amount" → kein amount-Feld mit confidence >= 0.55
    - "date"   → kein date-Feld mit confidence >= 0.50
    - "iban"   → IBAN confidence < 0.80 (truncated / validation failed)
    """
    uncertainties = []
    fields = analysis.extracted_fields
    doc_type = analysis.detected_document_type

    # type uncertainty
    if doc_type == "unknown":
        uncertainties.append("type")
    elif analysis.detection_debug:
        debug = analysis.detection_debug
        scores = debug.scores
        best_score = scores.get(doc_type, 0)
        runner_up = debug.runner_up
        if runner_up and runner_up != doc_type:
            runner_score = scores.get(runner_up, 0)
            if best_score > 0 and runner_score >= best_score * 0.70:
                uncertainties.append("type")

    # entity uncertainty
    suggestion = analysis.entity_suggestion
    if not suggestion.suggested_entity_id or suggestion.confidence < 0.45:
        uncertainties.append("entity")

    # amount uncertainty
    amount_keys = ["amount_total", "amount_due"]
    has_amount = any(
        _get_field(fields, k, min_confidence=0.55) for k in amount_keys
    )
    if not has_amount:
        uncertainties.append("amount")

    # date uncertainty
    date_keys = ["due_date", "document_date", "invoice_date", "incident_date", "offer_date", "contract_date"]
    has_date = any(
        _get_field(fields, k, min_confidence=0.50) for k in date_keys
    )
    if not has_date:
        uncertainties.append("date")

    # iban uncertainty
    iban_field = _get_field(fields, "iban", min_confidence=0.0)
    if iban_field and iban_field.confidence < 0.80:
        uncertainties.append("iban")

    return uncertainties


# ---------------------------------------------------------------------------
# RECOMMENDED FOCUS
# ---------------------------------------------------------------------------

def _recommended_focus(
    uncertainties: List[str],
    analysis: DocumentAnalysisResponse,
) -> str:
    """
    Gibt handlungsrelevanten Fokus zurück — oder leer.

    Reihenfolge:
    1. offene next_step-Decision → deren note (wenn vorhanden)
    2. höchste valide, handlungsrelevante Uncertainty → kurzer Klärfokus
    3. sonst leer

    Prinzip: Lieber ehrliche Lücke als halluzinierter Vorschlag.
    Nicht jede Unsicherheit braucht automatisch einen Fokus.
    """
    # Schritt 1: next_step-Decision (V2-Erweiterung — Platzhalter)
    # Wenn in Zukunft decision-Objekte im Analysis-Response existieren,
    # wird hier die offenste next_step-Decision mit note zurückgegeben.
    # Aktuell: kein decision-Layer in V1 → überspringen.

    # Schritt 2: handlungsrelevante Uncertainty
    # Priorisierung: entity > type > iban > amount > date
    # "amount" und "date" ohne entity-Kontext sind kein sinnvoller Fokus alleine.
    FOCUS_MAP = {
        "entity": "entity_unclear",
        "type":   "type_unclear",
        "iban":   "iban_check_required",
    }
    for key in ["entity", "type", "iban"]:
        if key in uncertainties:
            return FOCUS_MAP[key]

    # Schritt 3: leer
    return ""


# ---------------------------------------------------------------------------
# SENTENCE BUDGET — verbindlich
# ---------------------------------------------------------------------------

def _build_high_level_summary(
    doc_type: str,
    entity_name: Optional[str],
    entity_confidence: str,
    amount: Optional[str],
    primary_date: Optional[str],
    reference: Optional[str],
    uncertainties: List[str],
    source_quality: str,
) -> str:
    """
    Baut komprimierten Modellkontext-Satz. Max 3 Sätze, verbindlich.

    Satz 1 (immer): Typ + Entity + Betrag
    Satz 2 (wenn vorhanden): Datum + Referenz
    Satz 3 (nur wenn nötig): Unsicherheiten / Qualitätshinweis

    Sprache: ruhig, erfahren, nicht kumpelhaft, nicht autoritär.
    Keine Prozentzahlen. Confidence lebt in der Sprache.
    """
    parts = []

    # --- Satz 1: Typ + Entity + Betrag ---
    type_labels = {
        "invoice":        "Rechnung",
        "dunning":        "Mahnung",
        "penalty_notice": "Anonymverfügung",
        "offer":          "Angebot",
        "contract":       "Vertrag",
        "note":           "Notiz",
        "unknown":        "Dokument unbekannten Typs",
    }
    type_label = type_labels.get(doc_type, "Dokument")

    if entity_name and entity_confidence in ("high", "medium"):
        entity_part = f"von {entity_name}"
    elif entity_name and entity_confidence == "low":
        entity_part = f"vermutlich von {entity_name}"
    else:
        entity_part = "ohne zugeordnete Entity"

    if amount:
        s1 = f"{type_label} {entity_part}, Betrag {amount}."
    else:
        s1 = f"{type_label} {entity_part}, Betrag nicht eindeutig."
    parts.append(s1)

    # --- Satz 2: Datum + Referenz (nur wenn vorhanden) ---
    s2_parts = []
    if primary_date:
        s2_parts.append(f"Fällig/Datum: {primary_date}")
    if reference:
        s2_parts.append(f"Referenz: {reference}")
    if s2_parts:
        parts.append(", ".join(s2_parts) + ".")

    # --- Satz 3: Unsicherheiten / Qualitätshinweis (nur wenn nötig) ---
    notes = []
    if "type" in uncertainties:
        notes.append("Dokumenttyp unsicher")
    if "entity" in uncertainties:
        notes.append("Entity nicht eindeutig zuordenbar")
    if "iban" in uncertainties:
        notes.append("IBAN unvollständig — manuelle Prüfung")
    if source_quality in ("image_scan", "photo"):
        notes.append("Quelle: Foto/Scan")

    if notes:
        parts.append(". ".join(notes) + ".")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def compress(analysis: DocumentAnalysisResponse) -> DocumentSummary:
    """
    Nimmt DocumentAnalysisResponse, gibt DocumentSummary zurück.
    Kein DB-Zugriff. Keine Seiteneffekte.
    """
    fields = analysis.extracted_fields
    doc_type = analysis.detected_document_type

    # Entity
    suggestion = analysis.entity_suggestion
    entity_name = suggestion.suggested_entity_name
    entity_id = suggestion.suggested_entity_id
    entity_confidence = _bucket(suggestion.confidence)

    # Cold-Start: wenn confidence == 0 und kein Name → wirklich unbekannt
    if suggestion.confidence == 0.0:
        entity_name = None
        entity_id = None
        entity_confidence = "unknown"

    # Kernfelder
    amount = _amount_with_currency(fields, doc_type)
    primary_date = _primary_date(fields, doc_type)
    reference = _primary_reference(fields, doc_type)

    # Uncertainty
    uncertainties = _detect_uncertainties(analysis)
    has_open_decisions = len(uncertainties) > 0

    # Fokus
    recommended_focus = _recommended_focus(uncertainties, analysis)

    # Summary
    high_level_summary = _build_high_level_summary(
        doc_type=doc_type,
        entity_name=entity_name,
        entity_confidence=entity_confidence,
        amount=amount,
        primary_date=primary_date,
        reference=reference,
        uncertainties=uncertainties,
        source_quality=analysis.source_quality,
    )

    return DocumentSummary(
        document_id=analysis.document_id,
        document_type=doc_type,
        entity_name=entity_name,
        entity_id=entity_id,
        entity_confidence=entity_confidence,
        amount=amount,
        primary_date=primary_date,
        reference=reference,
        has_open_decisions=has_open_decisions,
        uncertainty_types=uncertainties,
        recommended_focus=recommended_focus,
        high_level_summary=high_level_summary,
    )
