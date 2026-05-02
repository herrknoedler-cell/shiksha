"""
SHIKSHA · ACCOUNTING ORCHESTRATOR + MATCHER V1
Stand: 25.04.2026

Verantwortung:
1. Matching-Engine: Score-basierter Vorschlag Bank-Buchung ↔ Rechnung
2. Sprache erzeugen über alle Match-/State-Outputs
3. Status-Übergänge durchführen (mit Audit)
4. Aging-Reports berechnen
5. Tageszusammenfassung erzeugen (analog SchoolState/CampState)

Architektur (V4-konform):
- Deterministisch, kein ML
- review_required = True per Default
- Sprache entsteht hier, nicht im Model
- Auch bei Score 100 keine automatische Buchung
"""

from datetime import date, datetime, timedelta
from typing import Optional
import re

from accounting_models import (
    AccountingInvoice, AccountingSignal, AccountingStateResponse,
    AgingBucket, AgingReport, BankTransaction, InvoiceStatusTransition,
    LanguageOutput, MatchProposal, ScoreBreakdown,
)


# ---------------------------------------------------------------------------
# 1. Sprach-Vokabular
# ---------------------------------------------------------------------------

LANGUAGE_TEMPLATES: dict[str, dict[str, str]] = {
    "accounting.match.high_confidence": {
        "flow":   "Match gefunden",
        "action": "Soll ich {entity} der Rechnung {invoice} zuordnen?",
        "alert":  "—",
    },
    "accounting.match.medium_confidence": {
        "flow":   "Wahrscheinlicher Match",
        "action": "Vermutlich {entity}. Stimmt das?",
        "alert":  "—",
    },
    "accounting.match.low_confidence": {
        "flow":   "Unklar",
        "action": "Für wen ist diese Buchung?",
        "alert":  "—",
    },
    "accounting.match.no_candidate": {
        "flow":   "Keine Rechnung gefunden",
        "action": "Eigene Verwendung oder ignorieren?",
        "alert":  "—",
    },
    "accounting.invoice.uploaded": {
        "flow":   "Rechnung verstanden",
        "action": "Stimmen die Felder?",
        "alert":  "—",
    },
    "accounting.invoice.duplicate_warning": {
        "flow":   "Diese Rechnung kennen wir",
        "action": "Trotzdem speichern?",
        "alert":  "—",
    },
    "accounting.invoice.iban_invalid": {
        "flow":   "IBAN unsicher",
        "action": "IBAN korrigieren?",
        "alert":  "—",
    },
    "accounting.invoice.partial_payment": {
        "flow":   "Teilzahlung — {amount}€ bleibt offen",
        "action": "Restbetrag nachfordern?",
        "alert":  "—",
    },
    "accounting.invoice.overdue": {
        "flow":   "{invoice} {days} Tage überfällig",
        "action": "Mahnstufe 1 vorbereiten?",
        "alert":  "{invoice} stark überfällig",
    },
    "accounting.invoice.partial_match_amount_off": {
        "flow":   "Betrag passt nicht ganz",
        "action": "{difference}€ Differenz — Skonto oder Tippfehler?",
        "alert":  "—",
    },
    "accounting.invoice.aged_no_match": {
        "flow":   "Keine Bewegung",
        "action": "Mit {entity} nachhaken?",
        "alert":  "—",
    },
    "accounting.import.complete": {
        "flow":   "{count} Buchungen importiert",
        "action": "—",
        "alert":  "—",
    },
}


# ---------------------------------------------------------------------------
# 2. Matching-Engine: Score-basiert
# ---------------------------------------------------------------------------

# Score-Konstanten
SCORE_IBAN_EXACT = 40
SCORE_AMOUNT_EXACT = 30
SCORE_AMOUNT_TOLERANCE = 20
SCORE_PURPOSE_INVOICE_NUMBER = 20
SCORE_PURPOSE_CUSTOMER_NAME = 10
SCORE_DATE_PLAUSIBLE = 10
SCORE_DATE_OUTSIDE = -10

# Schwellen
THRESHOLD_HIGH_CONFIDENCE = 90
THRESHOLD_MEDIUM_CONFIDENCE = 70
THRESHOLD_LOW_CONFIDENCE = 40

# Toleranzen
AMOUNT_EXACT_TOLERANCE_EUR = 0.01
AMOUNT_PCT_TOLERANCE = 0.01      # 1 %
DATE_WINDOW_DAYS = 90


def score_match(
    invoice: AccountingInvoice,
    transaction: BankTransaction,
) -> ScoreBreakdown:
    """
    Berechnet einen Match-Score zwischen Rechnung und Bank-Buchung.
    Returns: ScoreBreakdown mit Komponenten + Total.
    """
    breakdown = ScoreBreakdown()

    # 1. IBAN Match
    if invoice.iban and transaction.counterparty_iban:
        if invoice.iban.replace(" ", "").upper() == transaction.counterparty_iban.replace(" ", "").upper():
            breakdown.iban_match = SCORE_IBAN_EXACT

    # 2. Betrag-Match
    if invoice.amount_total is not None and invoice.outstanding_amount is not None:
        # Wir matchen primär gegen den outstanding_amount (z. B. nach Teilzahlung)
        target_amount = invoice.outstanding_amount if invoice.outstanding_amount > 0 else invoice.amount_total
        tx_abs = abs(transaction.amount)

        if abs(target_amount - tx_abs) <= AMOUNT_EXACT_TOLERANCE_EUR:
            breakdown.amount_match = SCORE_AMOUNT_EXACT
        elif target_amount > 0 and abs(target_amount - tx_abs) / target_amount <= AMOUNT_PCT_TOLERANCE:
            breakdown.amount_match = SCORE_AMOUNT_TOLERANCE

    # 3. Verwendungszweck enthält Rechnungs-Nr. / Kunden-Name
    if transaction.purpose:
        purpose_lower = transaction.purpose.lower()

        if invoice.invoice_number and invoice.invoice_number.lower() in purpose_lower:
            breakdown.purpose_match = SCORE_PURPOSE_INVOICE_NUMBER

        if invoice.customer_name:
            # match auch auf Teile des Namens (erste 2 Wörter)
            customer_tokens = invoice.customer_name.lower().split()[:2]
            if any(token in purpose_lower for token in customer_tokens if len(token) > 3):
                breakdown.customer_name_match = SCORE_PURPOSE_CUSTOMER_NAME

    # 4. Datum-Plausibilität
    if invoice.invoice_date and transaction.value_date:
        days_diff = (transaction.value_date - invoice.invoice_date).days
        if 0 <= days_diff <= DATE_WINDOW_DAYS:
            breakdown.date_plausibility = SCORE_DATE_PLAUSIBLE
        elif days_diff < 0 or days_diff > DATE_WINDOW_DAYS + 30:
            breakdown.counter_evidence = SCORE_DATE_OUTSIDE

    # Total
    breakdown.total = (
        breakdown.iban_match
        + breakdown.amount_match
        + breakdown.purpose_match
        + breakdown.customer_name_match
        + breakdown.date_plausibility
        + breakdown.counter_evidence  # negative
    )
    return breakdown


def proposals_for_transaction(
    transaction: BankTransaction,
    open_invoices: list[AccountingInvoice],
    max_proposals: int = 5,
) -> list[MatchProposal]:
    """
    Generiert Match-Vorschläge für eine Bank-Buchung gegen alle offenen Rechnungen.
    Sortiert nach Score absteigend, gibt nur die obersten max_proposals zurück.
    """
    candidates = []
    for inv in open_invoices:
        # Direction-Plausibilität: incoming-Rechnung erwartet ausgehende Buchung
        # outgoing-Rechnung erwartet eingehende Buchung
        if inv.direction == "incoming" and transaction.direction != "out":
            continue
        if inv.direction == "outgoing" and transaction.direction != "in":
            continue

        breakdown = score_match(inv, transaction)
        if breakdown.total <= 0:
            continue

        # Sprache wählen je nach Score
        if breakdown.total >= THRESHOLD_HIGH_CONFIDENCE:
            language_key = "accounting.match.high_confidence"
        elif breakdown.total >= THRESHOLD_MEDIUM_CONFIDENCE:
            language_key = "accounting.match.medium_confidence"
        elif breakdown.total >= THRESHOLD_LOW_CONFIDENCE:
            language_key = "accounting.match.low_confidence"
        else:
            continue  # zu schwach

        candidates.append(MatchProposal(
            id=f"prop_{transaction.id}_{inv.id}",
            bank_transaction_id=transaction.id,
            document_id=inv.id,
            score=breakdown.total,
            score_breakdown=breakdown,
            suggested_match_type="full",  # später verfeinern für partial / overpayment
            language_key=language_key,
            language_params={
                "entity": inv.customer_name or "—",
                "invoice": inv.invoice_number or inv.id,
            },
        ))

    candidates.sort(key=lambda p: p.score, reverse=True)
    return candidates[:max_proposals]


def proposals_for_all_unmatched(
    transactions: list[BankTransaction],
    open_invoices: list[AccountingInvoice],
) -> dict[str, list[MatchProposal]]:
    """Generiert Vorschläge für alle ungemachten Buchungen."""
    result = {}
    for tx in transactions:
        if tx.status != "unmatched":
            continue
        proposals = proposals_for_transaction(tx, open_invoices)
        if proposals:
            result[tx.id] = proposals
    return result


# ---------------------------------------------------------------------------
# 3. Status-Übergang nach Match-Bestätigung
# ---------------------------------------------------------------------------

def transition_after_match_acceptance(
    invoice: AccountingInvoice,
    matched_amount: float,
    operator: str,
    payment_match_id: str,
) -> tuple[AccountingInvoice, InvoiceStatusTransition]:
    """
    Berechnet den neuen Rechnungs-Zustand nach Match-Bestätigung.
    Gibt (aktualisierte_Rechnung, Übergang) zurück.
    """
    new_paid = invoice.paid_amount + matched_amount
    target = invoice.amount_total or 0
    new_outstanding = target - new_paid

    # Status entscheiden
    if abs(new_outstanding) <= 0.01:
        new_status = "paid"
        match_type = "full"
    elif new_outstanding > 0:
        new_status = "partially_matched"
        match_type = "partial"
    else:
        # Überzahlung
        new_status = "paid"
        match_type = "overpayment"

    transition = InvoiceStatusTransition(
        document_id=invoice.id,
        from_status=invoice.accounting_status,
        to_status=new_status,
        triggered_by=operator,
        payment_match_id=payment_match_id,
        notes=f"Match bestätigt: {matched_amount:.2f} {invoice.currency}",
        metadata={"match_type": match_type, "new_outstanding": new_outstanding},
    )

    # Aktualisierte Rechnung
    updated = invoice.model_copy(update={
        "paid_amount": new_paid,
        "outstanding_amount": max(0, new_outstanding),
        "accounting_status": new_status,
    })

    return updated, transition


# ---------------------------------------------------------------------------
# 4. Overdue-Detection (täglicher Cron-Kandidat)
# ---------------------------------------------------------------------------

def detect_overdue_transitions(
    invoices: list[AccountingInvoice],
    today: Optional[date] = None,
) -> list[InvoiceStatusTransition]:
    """
    Erkennt offene Rechnungen, deren Fälligkeit vorbei ist.
    Erzeugt 'overdue'-Übergänge — Operator entscheidet dann über Mahnstufen.
    """
    today = today or date.today()
    transitions: list[InvoiceStatusTransition] = []

    for inv in invoices:
        if inv.accounting_status not in ("open", "partially_matched"):
            continue
        if inv.due_date and inv.due_date < today:
            transitions.append(InvoiceStatusTransition(
                document_id=inv.id,
                from_status=inv.accounting_status,
                to_status="overdue",
                triggered_by="system_overdue_check",
                notes=f"Fällig seit {inv.due_date.isoformat()}, heute {today.isoformat()}",
            ))

    return transitions


# ---------------------------------------------------------------------------
# 5. Aging-Report
# ---------------------------------------------------------------------------

def build_aging_report(
    invoices: list[AccountingInvoice],
    direction: str = "outgoing",
    as_of: Optional[date] = None,
) -> AgingReport:
    """Baut einen Aging-Report (Buckets nach Tagen überfällig)."""
    as_of = as_of or date.today()

    buckets = {
        "future":  AgingBucket(label="future", description="noch nicht fällig"),
        "0_7":     AgingBucket(label="0_7", description="0–7 Tage überfällig"),
        "8_30":    AgingBucket(label="8_30", description="8–30 Tage überfällig"),
        "31_60":   AgingBucket(label="31_60", description="31–60 Tage überfällig"),
        "61_90":   AgingBucket(label="61_90", description="61–90 Tage überfällig"),
        "91_plus": AgingBucket(label="91_plus", description="über 90 Tage"),
    }

    relevant_invoices = [
        inv for inv in invoices
        if inv.direction == direction
        and inv.accounting_status in ("open", "partially_matched", "overdue", "reminder_1", "reminder_2", "reminder_3")
        and (inv.outstanding_amount or 0) > 0
    ]

    earliest_due = None
    oldest_id = None
    oldest_age = -1

    for inv in relevant_invoices:
        if not inv.due_date:
            continue
        days_overdue = (as_of - inv.due_date).days

        if earliest_due is None or inv.due_date < earliest_due:
            earliest_due = inv.due_date

        if days_overdue > oldest_age:
            oldest_age = days_overdue
            oldest_id = inv.id

        amount = inv.outstanding_amount or 0
        if days_overdue < 0:
            bucket = buckets["future"]
        elif days_overdue <= 7:
            bucket = buckets["0_7"]
        elif days_overdue <= 30:
            bucket = buckets["8_30"]
        elif days_overdue <= 60:
            bucket = buckets["31_60"]
        elif days_overdue <= 90:
            bucket = buckets["61_90"]
        else:
            bucket = buckets["91_plus"]

        bucket.count += 1
        bucket.total_amount += amount
        bucket.invoices.append(inv.id)

    total_open = sum(b.total_amount for b in buckets.values())

    return AgingReport(
        direction=direction,  # type: ignore
        as_of=as_of,
        buckets=list(buckets.values()),
        total_open_amount=total_open,
        oldest_open_invoice_id=oldest_id,
        earliest_due_date=earliest_due,
    )


# ---------------------------------------------------------------------------
# 6. Tageszusammenfassung (Sprache!)
# ---------------------------------------------------------------------------

def build_state_summary(
    open_invoices: list[AccountingInvoice],
    pending_proposals: list[MatchProposal],
    today_transactions: list[BankTransaction],
    today: Optional[date] = None,
) -> str:
    """
    Erzeugt eine 1-2-Satz-Tageszusammenfassung im SHIKSHA-Stil.
    Beispiele:
    - "Eurogast hat 106,40€ bezahlt — passt zur Rechnung 4421. VLV 75,22€ raus, Mahnung beglichen."
    - "Drei Buchungen ungematched. Schauen wir gemeinsam? Sonst 4 Rechnungen offen, 2.398€ insgesamt."
    """
    today = today or date.today()

    parts = []

    # 1. Heutige Transaktionen
    incoming_today = [t for t in today_transactions if t.value_date == today and t.amount > 0]
    outgoing_today = [t for t in today_transactions if t.value_date == today and t.amount < 0]

    if incoming_today:
        total_in = sum(t.amount for t in incoming_today)
        parts.append(f"{len(incoming_today)} Eingang{'e' if len(incoming_today) > 1 else ''} heute, +{total_in:.2f}€")
    if outgoing_today:
        total_out = abs(sum(t.amount for t in outgoing_today))
        parts.append(f"{len(outgoing_today)} Ausgang{'e' if len(outgoing_today) > 1 else ''} heute, −{total_out:.2f}€")

    # 2. Pending Proposals
    high_proposals = [p for p in pending_proposals if p.score >= THRESHOLD_HIGH_CONFIDENCE]
    if high_proposals:
        parts.append(f"{len(high_proposals)} sicherer Match{'es' if len(high_proposals) > 1 else ''} wartet")
    elif pending_proposals:
        parts.append(f"{len(pending_proposals)} Matches zum Prüfen")

    # 3. Offene Posten total
    open_total = sum(inv.outstanding_amount or 0 for inv in open_invoices)
    open_count = len([inv for inv in open_invoices if (inv.outstanding_amount or 0) > 0])
    if open_count:
        parts.append(f"{open_count} offen, {open_total:.0f}€ insgesamt")

    # 4. Überfällige
    overdue = [inv for inv in open_invoices if inv.days_overdue and inv.days_overdue > 0]
    if overdue:
        oldest = max(overdue, key=lambda i: i.days_overdue or 0)
        parts.append(f"älteste Mahnung: {oldest.days_overdue} Tage")

    if not parts:
        return "Heute alles ruhig. Keine offenen Posten, keine Bewegung."

    return ". ".join(parts) + "."


# ---------------------------------------------------------------------------
# 7. Hauptfunktion: State
# ---------------------------------------------------------------------------

def build_accounting_state(
    open_invoices: list[AccountingInvoice],
    pending_proposals: list[MatchProposal],
    today_transactions: list[BankTransaction],
    organization_id: Optional[str] = None,
    direction: Optional[str] = None,
) -> AccountingStateResponse:
    """Stellt den vollständigen Accounting-State zusammen."""
    summary = build_state_summary(open_invoices, pending_proposals, today_transactions)

    open_count = len([inv for inv in open_invoices if (inv.outstanding_amount or 0) > 0])
    open_total = sum(inv.outstanding_amount or 0 for inv in open_invoices)

    aging = None
    if direction:
        aging = build_aging_report(open_invoices, direction=direction)

    language = LanguageOutput(
        mode="flow",
        text_key="accounting.state.overview",
        params={"summary": summary},
        priority="medium",
    )

    return AccountingStateResponse(
        summary=summary,
        open_invoices_count=open_count,
        open_invoices_total_eur=open_total,
        pending_match_proposals=len(pending_proposals),
        aging=aging,
        recent_signals=[],
        review_required=True,
        language=language,
    )


# ---------------------------------------------------------------------------
# 8. IBAN-Validator (V4-konform, hier kompakt)
# ---------------------------------------------------------------------------

IBAN_LENGTHS: dict[str, int] = {
    "AT": 20, "DE": 22, "CH": 21, "GB": 22, "FR": 27,
    "NL": 18, "BE": 16, "IT": 27, "ES": 24,
}


def validate_iban(iban: Optional[str]) -> tuple[bool, float, Optional[str]]:
    """Returns: (is_structurally_valid, confidence, note)"""
    if not iban:
        return (False, 0.0, "iban_missing")

    cleaned = iban.replace(" ", "").upper()
    if len(cleaned) < 4:
        return (False, 0.0, "iban_too_short")

    country = cleaned[:2]
    expected_len = IBAN_LENGTHS.get(country)

    if expected_len is None:
        return (False, 0.5, f"iban_unknown_country: {country}")

    if len(cleaned) == expected_len:
        return (True, 0.92, None)
    elif len(cleaned) < expected_len:
        return (False, 0.35, f"truncated: {len(cleaned)}/{expected_len} chars — manual check required")
    else:
        return (False, 0.2, f"too_long: {len(cleaned)}/{expected_len} chars")


__all__ = [
    "LANGUAGE_TEMPLATES",
    "SCORE_IBAN_EXACT", "SCORE_AMOUNT_EXACT", "SCORE_PURPOSE_INVOICE_NUMBER",
    "THRESHOLD_HIGH_CONFIDENCE", "THRESHOLD_MEDIUM_CONFIDENCE", "THRESHOLD_LOW_CONFIDENCE",
    "score_match", "proposals_for_transaction", "proposals_for_all_unmatched",
    "transition_after_match_acceptance", "detect_overdue_transitions",
    "build_aging_report", "build_state_summary", "build_accounting_state",
    "validate_iban",
]
