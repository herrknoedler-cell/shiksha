"""
SHIKSHA · compression.py · V1 Skizze
Stand: 25.04.2026

V4-Roadmap-Punkt 5: high_level_summary-Modul.
V4-Architektur-Entscheidung 16: formulator.py = 1 UI-Satz / compression.py = Modellkontext

Trennung:
- formulator.py erzeugt EINEN UI-Satz für den Operator
  ("Mahnung von ARAG. 1.488€ fällig 9. Mai. Soll ich das zuordnen?")

- compression.py (DIESES MODUL) erzeugt einen MODELL-KONTEXT —
  eine kompakte strukturierte Darstellung des Dokuments,
  geeignet für LLM-Prompt-Inklusion bei Multi-Dokument-Aufgaben.

Use-Cases:
1. „Was liegt bei Lunchbox Gastro alles offen?" → 8 Dokumente komprimiert
2. „Was hat sich seit letzter Woche getan?" → Aktivitäts-Stream komprimiert
3. „Soll ich Werner Hofbauer schreiben?" → Werner-Kontext + relevantes letztes Dokument komprimiert
4. „Was ist heute zu tun?" → Tageszusammenfassung über alle aktiven Editionen

V1-Beschränkungen (bewusst):
- Keine LLM-Aufrufe in V1 — wir nutzen template-basiertes Sammeln
- Lokaler Algorithmus, deterministisch, schnell
- LLM-Erweiterung in V2, sobald wir Latenz/Kosten messen können
"""

from datetime import date, datetime, timedelta
from typing import Optional, Any, Literal
from dataclasses import dataclass, field, asdict


# ---------------------------------------------------------------------------
# 1. Datenmodelle
# ---------------------------------------------------------------------------

@dataclass
class DocumentDigest:
    """Kompakte Darstellung eines Dokuments für Modellkontext."""
    doc_id: str
    doc_type: str
    edition: Optional[str] = None
    organization_id: Optional[str] = None
    primary_entity: Optional[str] = None    # Wer ist hauptsächlich betroffen
    summary_keys: dict[str, Any] = field(default_factory=dict)  # ein-/zweistellige Felder
    severity: Literal["high", "mid", "low", "info"] = "info"
    deadline: Optional[date] = None
    amount_eur: Optional[float] = None
    age_days: Optional[int] = None
    one_line: Optional[str] = None          # eine Sprachzeile, je nach Typ

    def to_prompt_line(self) -> str:
        """Eine Zeile für den LLM-Prompt — sehr kompakt."""
        parts = [f"{self.doc_type}"]
        if self.primary_entity:
            parts.append(f"@{self.primary_entity}")
        if self.amount_eur:
            parts.append(f"{self.amount_eur:.2f}€")
        if self.deadline:
            parts.append(f"due:{self.deadline.isoformat()}")
        if self.severity != "info":
            parts.append(f"sev:{self.severity}")
        return " | ".join(parts)


@dataclass
class HighLevelSummary:
    """Sprachfähige High-Level-Zusammenfassung über mehrere Dokumente."""
    scope: str                              # was wurde zusammengefasst (Entity / Zeitraum / Edition)
    one_sentence: str                       # 1 Sentenz für UI
    key_concerns: list[str] = field(default_factory=list)  # 1-3 wichtigste Themen
    document_count: int = 0
    total_open_amount_eur: Optional[float] = None
    earliest_deadline: Optional[date] = None
    digests: list[DocumentDigest] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    def to_prompt_block(self) -> str:
        """Multi-Line-Block für LLM-Prompt."""
        lines = [f"# {self.scope}", f"summary: {self.one_sentence}"]
        if self.total_open_amount_eur:
            lines.append(f"open: {self.total_open_amount_eur:.2f}€")
        if self.earliest_deadline:
            lines.append(f"earliest_deadline: {self.earliest_deadline.isoformat()}")
        if self.key_concerns:
            lines.append("concerns:")
            for c in self.key_concerns:
                lines.append(f"  - {c}")
        if self.digests:
            lines.append(f"docs ({len(self.digests)}):")
            for d in self.digests[:10]:  # max 10 für Kontext-Limits
                lines.append(f"  - {d.to_prompt_line()}")
            if len(self.digests) > 10:
                lines.append(f"  ... und {len(self.digests) - 10} weitere")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Document → Digest (per Typ)
# ---------------------------------------------------------------------------

def compress_invoice(doc: dict) -> DocumentDigest:
    fields = doc.get("fields", {})
    amount = fields.get("amount_total")
    deadline = fields.get("due_date")
    return DocumentDigest(
        doc_id=doc["id"],
        doc_type="invoice",
        primary_entity=fields.get("customer_name"),
        deadline=parse_date(deadline) if deadline else None,
        amount_eur=float(amount) if amount else None,
        severity="mid" if not doc.get("paid_at") else "info",
        summary_keys={
            "invoice_number": fields.get("invoice_number"),
            "currency": fields.get("currency", "EUR"),
        },
    )


def compress_dunning(doc: dict) -> DocumentDigest:
    fields = doc.get("fields", {})
    amount = fields.get("amount_due")
    deadline = fields.get("due_date")
    level = fields.get("reminder_level", 1)
    severity_map = {1: "mid", 2: "high", 3: "high"}
    return DocumentDigest(
        doc_id=doc["id"],
        doc_type="dunning",
        primary_entity=fields.get("customer_name"),
        deadline=parse_date(deadline) if deadline else None,
        amount_eur=float(amount) if amount else None,
        severity=severity_map.get(level, "high"),
        summary_keys={
            "reference_invoice": fields.get("referenced_invoice_number"),
            "level": level,
        },
    )


def compress_enrollment_form(doc: dict) -> DocumentDigest:
    fields = doc.get("fields", {})
    is_minor = fields.get("is_minor", False)
    consents = fields.get("consents", [])
    consent_complete = all(c.get("granted") for c in consents) if consents else True
    return DocumentDigest(
        doc_id=doc["id"],
        doc_type="enrollment_form",
        primary_entity=fields.get("student_name"),
        severity="mid" if is_minor and not consent_complete else "info",
        summary_keys={
            "course": fields.get("course_selected"),
            "is_minor": is_minor,
            "consent_complete": consent_complete,
        },
    )


def compress_meter_reading(doc: dict) -> DocumentDigest:
    fields = doc.get("fields", {})
    anomaly = fields.get("anomaly_flag", False)
    return DocumentDigest(
        doc_id=doc["id"],
        doc_type="meter_reading",
        primary_entity=fields.get("pitch_or_unit_id"),
        severity="mid" if anomaly else "info",
        summary_keys={
            "value": fields.get("reading_value"),
            "consumption": fields.get("consumption_since_previous"),
            "anomaly": anomaly,
        },
    )


def compress_behoerden_bescheid(doc: dict) -> DocumentDigest:
    fields = doc.get("fields", {})
    deadline = fields.get("deadline") or fields.get("fees_due_date")
    auflagen_count = len(fields.get("auflagen", []))
    fees = fields.get("fees")
    return DocumentDigest(
        doc_id=doc["id"],
        doc_type="behoerden_bescheid",
        primary_entity=fields.get("authority_name"),
        deadline=parse_date(deadline) if deadline else None,
        amount_eur=float(fees) if fees else None,
        severity="high" if auflagen_count > 0 or fees else "mid",
        summary_keys={
            "case_number": fields.get("case_number"),
            "auflagen_count": auflagen_count,
        },
    )


def compress_delivery_note(doc: dict) -> DocumentDigest:
    fields = doc.get("fields", {})
    return DocumentDigest(
        doc_id=doc["id"],
        doc_type="delivery_note",
        primary_entity=fields.get("supplier_name"),
        amount_eur=float(fields.get("total_amount", 0)) if fields.get("total_amount") else None,
        severity="info",
        summary_keys={
            "delivery_date": str(fields.get("delivery_date", "")),
            "items_count": len(fields.get("items", [])),
        },
    )


def compress_weather_postponement(doc: dict) -> DocumentDigest:
    fields = doc.get("fields", {})
    return DocumentDigest(
        doc_id=doc["id"],
        doc_type="weather_postponement",
        primary_entity=fields.get("affected_session_name"),
        severity="mid",
        summary_keys={
            "reason": fields.get("weather_reason"),
            "affected_count": fields.get("affected_recipients_count"),
            "new_date": str(fields.get("new_session_date", "")),
        },
    )


def compress_guest_complaint(doc: dict) -> DocumentDigest:
    fields = doc.get("fields", {})
    sev = fields.get("severity_self_reported", "low")
    return DocumentDigest(
        doc_id=doc["id"],
        doc_type="guest_complaint",
        primary_entity=fields.get("guest_name"),
        severity=sev if sev in ("low", "mid", "high") else "low",
        summary_keys={
            "target": fields.get("complaint_target"),
            "received_via": fields.get("received_via"),
        },
    )


def compress_reservation_confirmation(doc: dict) -> DocumentDigest:
    fields = doc.get("fields", {})
    return DocumentDigest(
        doc_id=doc["id"],
        doc_type="reservation_confirmation",
        primary_entity=fields.get("customer_name"),
        amount_eur=float(fields.get("total_amount", 0)) if fields.get("total_amount") else None,
        deadline=parse_date(fields.get("from_date")) if fields.get("from_date") else None,
        severity="info",
        summary_keys={
            "pitch": fields.get("pitch_or_resource"),
            "nights": fields.get("nights"),
            "deposit_paid": fields.get("deposit_paid", False),
        },
    )


# ---------------------------------------------------------------------------
# 3. Dispatcher
# ---------------------------------------------------------------------------

COMPRESSION_DISPATCH = {
    "invoice": compress_invoice,
    "dunning": compress_dunning,
    "enrollment_form": compress_enrollment_form,
    "meter_reading": compress_meter_reading,
    "behoerden_bescheid": compress_behoerden_bescheid,
    "delivery_note": compress_delivery_note,
    "weather_postponement": compress_weather_postponement,
    "guest_complaint": compress_guest_complaint,
    "reservation_confirmation": compress_reservation_confirmation,
}


def compress_document(doc: dict) -> DocumentDigest:
    """Hauptfunktion — verkleinert ein Dokument auf Modell-Kontext-Größe."""
    doc_type = doc.get("type", "unknown")
    func = COMPRESSION_DISPATCH.get(doc_type)
    if func:
        digest = func(doc)
    else:
        digest = DocumentDigest(
            doc_id=doc.get("id", "?"),
            doc_type=doc_type,
            severity="info",
        )

    # Allgemeine Felder
    digest.edition = doc.get("edition")
    digest.organization_id = doc.get("organization_id")
    if doc.get("created_at"):
        try:
            created_at = datetime.fromisoformat(doc["created_at"]) if isinstance(doc["created_at"], str) else doc["created_at"]
            digest.age_days = (datetime.now() - created_at).days
        except Exception:
            pass

    return digest


# ---------------------------------------------------------------------------
# 4. High-Level-Summary über mehrere Dokumente
# ---------------------------------------------------------------------------

def build_high_level_summary(
    docs: list[dict],
    scope: str = "general",
    max_concerns: int = 3,
) -> HighLevelSummary:
    """
    Generiert eine sprachfähige High-Level-Zusammenfassung aus mehreren Dokumenten.

    Beispiel-Aufrufe:
    - build_high_level_summary(docs_lunchbox, scope="Lunchbox Gastro GmbH")
      → "8 offene Posten, 2.398€ insgesamt. Älteste Mahnung 13 Tage."
    - build_high_level_summary(docs_today, scope="Heute")
      → "Drei Sachen: Werner zahlt nicht, Klara hat probiert, Bernds Karte läuft bald."
    """
    digests = [compress_document(d) for d in docs]

    # Aggregat-Berechnung
    total_open = sum(d.amount_eur for d in digests if d.amount_eur is not None and d.severity in ("mid", "high"))
    deadlines = [d.deadline for d in digests if d.deadline is not None]
    earliest = min(deadlines) if deadlines else None

    # Concerns: die wichtigsten Severity-Themen
    severity_score = {"high": 3, "mid": 2, "low": 1, "info": 0}
    sorted_digests = sorted(digests, key=lambda d: (severity_score.get(d.severity, 0), -(d.age_days or 0)), reverse=True)

    concerns = []
    for d in sorted_digests[:max_concerns]:
        concern = _concern_phrase(d)
        if concern:
            concerns.append(concern)

    # 1-Satz-Summary erzeugen
    one_sentence = _one_sentence_summary(digests, total_open, earliest)

    return HighLevelSummary(
        scope=scope,
        one_sentence=one_sentence,
        key_concerns=concerns,
        document_count=len(digests),
        total_open_amount_eur=total_open if total_open > 0 else None,
        earliest_deadline=earliest,
        digests=digests,
    )


def _concern_phrase(d: DocumentDigest) -> str:
    """Eine kurze Concern-Phrase pro Document-Typ."""
    if d.doc_type == "dunning":
        ent = d.primary_entity or "Jemand"
        amt = f"{d.amount_eur:.0f}€" if d.amount_eur else ""
        return f"Mahnung an {ent} {amt}".strip()
    if d.doc_type == "behoerden_bescheid":
        ent = d.primary_entity or "Behörde"
        return f"{ent} mit Auflage / Fälligkeit"
    if d.doc_type == "weather_postponement":
        return f"Wetter-Verschiebung kommuniziert"
    if d.doc_type == "guest_complaint":
        ent = d.primary_entity or "Gast"
        return f"Beschwerde von {ent}"
    if d.doc_type == "meter_reading" and d.summary_keys.get("anomaly"):
        ent = d.primary_entity or "Pitch"
        return f"Strom-Anomalie {ent}"
    if d.doc_type == "enrollment_form" and d.severity == "mid":
        return f"Konsent-Lücke bei Anmeldung"
    return ""


def _one_sentence_summary(
    digests: list[DocumentDigest],
    total_open: float,
    earliest_deadline: Optional[date],
) -> str:
    """Erzeugt eine 1-Satz-Zusammenfassung im SHIKSHA-Stil."""
    if not digests:
        return "Nichts offen."

    high = sum(1 for d in digests if d.severity == "high")
    mid = sum(1 for d in digests if d.severity == "mid")

    parts = []
    if high > 0:
        parts.append(f"{high} Sache{'n' if high > 1 else ''} drücken")
    if mid > 0:
        parts.append(f"{mid} Hinweis{'e' if mid > 1 else ''}")

    if total_open > 0:
        parts.append(f"{total_open:.0f}€ offen")

    if earliest_deadline:
        days_until = (earliest_deadline - date.today()).days
        if days_until < 0:
            parts.append("Frist abgelaufen")
        elif days_until == 0:
            parts.append("eine Frist heute")
        elif days_until <= 7:
            parts.append(f"nächste Frist in {days_until} Tagen")

    if not parts:
        return "Heute alles ruhig."

    return ", ".join(parts) + "."


# ---------------------------------------------------------------------------
# 5. Utility
# ---------------------------------------------------------------------------

def parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except Exception:
            try:
                # German date "DD.MM.YYYY"
                d, m, y = value.split(".")
                return date(int(y), int(m), int(d))
            except Exception:
                return None
    return None


# ---------------------------------------------------------------------------
# 6. Demo / Test
# ---------------------------------------------------------------------------

def demo_compression():
    """Demo-Aufruf: Mini-Test mit fiktivem Lunchbox-Kontext."""
    docs = [
        {
            "id": "doc_1", "type": "dunning",
            "edition": "business.shiksha",
            "fields": {
                "customer_name": "Lichtquelle Wien",
                "amount_due": 115.00,
                "due_date": "2026-05-06",
                "reminder_level": 1,
                "referenced_invoice_number": "2026-0298",
            },
            "created_at": (datetime.now() - timedelta(days=13)).isoformat(),
        },
        {
            "id": "doc_2", "type": "invoice",
            "fields": {
                "customer_name": "Lichtquelle Wien",
                "amount_total": 535.02,
                "due_date": "2026-01-31",
                "invoice_number": "2026-WS-118-0892",
            },
            "created_at": (datetime.now() - timedelta(days=120)).isoformat(),
        },
        {
            "id": "doc_3", "type": "behoerden_bescheid",
            "fields": {
                "authority_name": "Gesundheitsamt Berchtesgadener Land",
                "deadline": "2026-06-01",
                "fees": None,
                "auflagen": ["Pool-Antirutsch erneuern", "Aufsichtsplan digital"],
                "case_number": "GBL-2026-Pool-022",
            },
            "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
        },
    ]

    summary = build_high_level_summary(docs, scope="Camping Allweglehen — heute")

    print(f'Scope: {summary.scope}')
    print(f'Summary: "{summary.one_sentence}"')
    print(f'Concerns:')
    for c in summary.key_concerns:
        print(f'  - {c}')
    print(f'Total open: {summary.total_open_amount_eur}€')
    print(f'Earliest deadline: {summary.earliest_deadline}')
    print()
    print("--- Prompt-Block ---")
    print(summary.to_prompt_block())


if __name__ == "__main__":
    demo_compression()


__all__ = [
    "DocumentDigest",
    "HighLevelSummary",
    "compress_document",
    "build_high_level_summary",
    "COMPRESSION_DISPATCH",
]
