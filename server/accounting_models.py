"""
SHIKSHA · ACCOUNTING MODUL · Pydantic Models V1
Stand: 25.04.2026
"""

from datetime import date, datetime
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Enums
# ---------------------------------------------------------------------------

InvoiceDirection = Literal["incoming", "outgoing"]
AccountingStatus = Literal[
    "open", "matched", "partially_matched", "paid",
    "overdue", "reminder_1", "reminder_2", "reminder_3",
    "written_off", "disputed", "archived",
]
TransactionStatus = Literal["unmatched", "matched", "partially_matched", "ignored", "review"]
TransactionDirection = Literal["in", "out"]
TransactionType = Literal[
    "sepa_credit", "sepa_debit", "card", "cash",
    "standing_order", "fee", "interest", "other",
]
StatementFormat = Literal["csv", "camt053", "mt940"]
MatchType = Literal["full", "partial", "overpayment", "underpayment_skonto"]
ProposalStatus = Literal["pending", "accepted", "rejected", "superseded"]
SignalSeverity = Literal["high", "mid", "low", "info"]


# ---------------------------------------------------------------------------
# 2. Bank-Transaction
# ---------------------------------------------------------------------------

class BankTransaction(BaseModel):
    id: str
    statement_import_id: Optional[str] = None
    iban_account: str                                 # eigenes Konto
    booking_date: Optional[date] = None
    value_date: date
    amount: float                                     # + Eingang, - Ausgang
    currency: str = "EUR"
    counterparty_name: Optional[str] = None
    counterparty_iban: Optional[str] = None
    counterparty_bic: Optional[str] = None
    purpose: Optional[str] = None
    bank_reference: Optional[str] = None
    transaction_type: Optional[TransactionType] = None
    status: TransactionStatus = "unmatched"
    raw_record: Optional[dict] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def direction(self) -> TransactionDirection:
        return "in" if self.amount > 0 else "out"


# ---------------------------------------------------------------------------
# 3. Statement-Import
# ---------------------------------------------------------------------------

class StatementImport(BaseModel):
    id: str
    file_name: str
    file_format: StatementFormat
    bank_profile: Optional[str] = None
    iban_account: str
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    transactions_count: int = 0
    new_count: int = 0
    duplicate_count: int = 0
    parse_errors: int = 0
    imported_at: datetime = Field(default_factory=datetime.now)
    imported_by: Optional[str] = None
    file_hash: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 4. Match Proposal & Confirmed Match
# ---------------------------------------------------------------------------

class ScoreBreakdown(BaseModel):
    iban_match: int = 0
    amount_match: int = 0
    purpose_match: int = 0
    date_plausibility: int = 0
    customer_name_match: int = 0
    counter_evidence: int = 0                          # negative penalties
    total: int = 0


class MatchProposal(BaseModel):
    id: str
    bank_transaction_id: str
    document_id: str
    score: int                                         # 0-100
    score_breakdown: Optional[ScoreBreakdown] = None
    suggested_match_type: MatchType = "full"
    language_key: Optional[str] = None
    language_params: dict = Field(default_factory=dict)
    status: ProposalStatus = "pending"
    created_at: datetime = Field(default_factory=datetime.now)
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decision_notes: Optional[str] = None


class PaymentMatch(BaseModel):
    """Bestätigte Verknüpfung Bank-Buchung ↔ Rechnung."""
    id: str
    bank_transaction_id: str
    document_id: str
    match_type: MatchType
    matched_amount: float
    score: Optional[int] = None
    score_breakdown: Optional[ScoreBreakdown] = None
    confirmed_by: str
    confirmed_at: datetime = Field(default_factory=datetime.now)
    notes: Optional[str] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    revoke_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# 5. Invoice-Status-Übergänge
# ---------------------------------------------------------------------------

class InvoiceStatusTransition(BaseModel):
    id: Optional[int] = None
    document_id: str
    from_status: Optional[AccountingStatus] = None
    to_status: AccountingStatus
    triggered_by: str                                  # 'operator' | 'system_auto_match_proposal' | 'system_overdue_check'
    triggered_at: datetime = Field(default_factory=datetime.now)
    payment_match_id: Optional[str] = None
    notes: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 6. Invoice-Sicht (composite über documents-Tabelle + accounting-Felder)
# ---------------------------------------------------------------------------

class AccountingInvoice(BaseModel):
    """Lese-Sicht über die V4-`documents`-Tabelle, ergänzt um Accounting-Felder."""
    id: str                                            # documents.id
    document_type: Literal["invoice", "dunning"]
    direction: InvoiceDirection
    customer_name: Optional[str] = None
    customer_id: Optional[str] = None                  # Link zu customers
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    amount_total: Optional[float] = None
    paid_amount: float = 0.0
    outstanding_amount: Optional[float] = None
    currency: str = "EUR"
    iban: Optional[str] = None
    accounting_status: AccountingStatus = "open"
    reminder_level: int = 0
    reminder_last_sent_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)

    @property
    def days_until_due(self) -> Optional[int]:
        if not self.due_date:
            return None
        return (self.due_date - date.today()).days

    @property
    def days_overdue(self) -> Optional[int]:
        if not self.due_date:
            return None
        days = (date.today() - self.due_date).days
        return days if days > 0 else 0


# ---------------------------------------------------------------------------
# 7. Accounting-Signals
# ---------------------------------------------------------------------------

class AccountingSignal(BaseModel):
    id: Optional[int] = None
    organization_id: Optional[str] = None
    edition: Optional[str] = None
    signal_key: str
    severity: SignalSeverity = "info"
    params: dict = Field(default_factory=dict)
    document_id: Optional[str] = None
    bank_transaction_id: Optional[str] = None
    status: Literal["open", "acknowledged", "resolved", "ignored"] = "open"
    created_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None


# ---------------------------------------------------------------------------
# 8. Aging-Bucket (für Auswertung)
# ---------------------------------------------------------------------------

class AgingBucket(BaseModel):
    label: Literal["future", "0_7", "8_30", "31_60", "61_90", "91_plus"]
    description: str
    count: int = 0
    total_amount: float = 0.0
    invoices: list[str] = Field(default_factory=list)


class AgingReport(BaseModel):
    direction: InvoiceDirection
    as_of: date
    buckets: list[AgingBucket]
    total_open_amount: float
    oldest_open_invoice_id: Optional[str] = None
    earliest_due_date: Optional[date] = None


# ---------------------------------------------------------------------------
# 9. Sprachausgabe
# ---------------------------------------------------------------------------

class LanguageOutput(BaseModel):
    mode: Literal["flow", "action", "alert"] = "flow"
    text_key: str
    params: dict = Field(default_factory=dict)
    priority: Literal["low", "medium", "high"] = "medium"


# ---------------------------------------------------------------------------
# 10. Request/Response
# ---------------------------------------------------------------------------

class StatementUploadRequest(BaseModel):
    file_format: StatementFormat
    bank_profile: Optional[str] = None
    iban_account: str
    file_content_b64: str                              # base64-encoded


class StatementUploadResponse(BaseModel):
    statement_import: StatementImport
    new_transactions: list[BankTransaction] = Field(default_factory=list)
    duplicate_transactions: list[BankTransaction] = Field(default_factory=list)
    new_match_proposals: list[MatchProposal] = Field(default_factory=list)
    language: LanguageOutput


class MatchAcceptRequest(BaseModel):
    proposal_id: str
    confirmed_by: str
    match_type_override: Optional[MatchType] = None
    notes: Optional[str] = None


class MatchManualRequest(BaseModel):
    bank_transaction_id: str
    document_id: str
    matched_amount: Optional[float] = None             # default: voller Bank-Betrag
    confirmed_by: str
    notes: Optional[str] = None


class AccountingStateRequest(BaseModel):
    organization_id: Optional[str] = None
    direction: Optional[InvoiceDirection] = None
    focus: Literal["overview", "today", "overdue", "matching", "aging"] = "overview"


class AccountingStateResponse(BaseModel):
    summary: str
    open_invoices_count: int
    open_invoices_total_eur: float
    pending_match_proposals: int
    aging: Optional[AgingReport] = None
    recent_signals: list[AccountingSignal] = Field(default_factory=list)
    review_required: bool = True
    language: LanguageOutput
    as_of: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# 11. Modul-Profile
# ---------------------------------------------------------------------------

ACCOUNTING_MODULE_PROFILE: dict[str, Any] = {
    "module": "accounting",
    "version": "1.0.0",
    "scope": "cross-edition",
    "applicable_editions": ["business.shiksha", "schule.shiksha", "camping.shiksha", "club.shiksha"],
    "is_phase_1_required": True,
    "supported_statement_formats": ["csv", "camt053", "mt940"],
    "supported_bank_profiles": [
        "hypo_vorarlberg",
        "sparkasse_bgl",
        "erste_bank_at",
        "raiffeisen_lb_tirol",
        "nord_ostsee_sparkasse",
        "generic_csv",
    ],
    "review_required_default": True,
}


__all__ = [
    "InvoiceDirection", "AccountingStatus", "TransactionStatus", "TransactionDirection",
    "TransactionType", "StatementFormat", "MatchType", "ProposalStatus", "SignalSeverity",
    "BankTransaction", "StatementImport", "ScoreBreakdown",
    "MatchProposal", "PaymentMatch", "InvoiceStatusTransition", "AccountingInvoice",
    "AccountingSignal", "AgingBucket", "AgingReport", "LanguageOutput",
    "StatementUploadRequest", "StatementUploadResponse",
    "MatchAcceptRequest", "MatchManualRequest",
    "AccountingStateRequest", "AccountingStateResponse",
    "ACCOUNTING_MODULE_PROFILE",
]


# ==========================================================================
# V4-Compat-Stubs (für main.py-Imports bis zur V2-Migration)
# main.py importiert diese seit V4. Werden in V2 in den accounting_router
# überführt, vorerst Stubs damit der Import-Pfad nicht crasht.
# ==========================================================================

class LedgerFromDocumentRequest(BaseModel):
    """V4-Stub. Wird in V2 durch /accounting/invoices/upload ersetzt."""
    document_id: str
    notes: Optional[str] = None


class PaymentConfirmRequest(BaseModel):
    """V4-Stub. Wird in V2 durch /accounting/match/proposals/{id}/accept ersetzt."""
    payment_id: str
    confirmed_by: str
    notes: Optional[str] = None


# ==========================================================================
# V4-Compat-Stubs · Block 2/2 (für accounting_module.py)
# Ergänzt LedgerEntry, OpenItem, MonthlySummary etc. damit der V4-Service-Pfad
# wieder läuft. Werden in V2 sauber durch die Match-Engine ersetzt.
# ==========================================================================

class LedgerEntry(BaseModel):
    """V4-Stub. Hauptbuch-Eintrag."""
    id: str
    document_id: Optional[str] = None
    entry_date: Optional[date] = None
    amount: float
    currency: str = "EUR"
    direction: Optional[str] = None  # 'in' | 'out'
    description: Optional[str] = None
    customer_id: Optional[str] = None
    edition: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class LedgerEntryCreate(BaseModel):
    """V4-Stub. Request zum Anlegen eines Ledger-Eintrags."""
    document_id: Optional[str] = None
    entry_date: Optional[date] = None
    amount: float
    currency: str = "EUR"
    direction: Optional[str] = None
    description: Optional[str] = None
    customer_id: Optional[str] = None
    edition: Optional[str] = None


class PaymentConfirmResponse(BaseModel):
    """V4-Stub. Antwort auf Zahlungsbestätigung."""
    payment_id: str
    status: str = "confirmed"
    confirmed_at: datetime = Field(default_factory=datetime.now)
    notes: Optional[str] = None


class PaymentRecord(BaseModel):
    """V4-Stub. Einzelne Zahlungsbuchung."""
    id: str
    ledger_entry_id: Optional[str] = None
    amount: float
    currency: str = "EUR"
    payment_date: Optional[date] = None
    method: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None


class OpenItem(BaseModel):
    """V4-Stub. Offener Posten in der Übersicht."""
    id: str
    document_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    amount: float
    currency: str = "EUR"
    due_date: Optional[date] = None
    days_overdue: Optional[int] = None
    description: Optional[str] = None


class OpenItemsResponse(BaseModel):
    """V4-Stub. Liste der offenen Posten."""
    items: list[OpenItem] = Field(default_factory=list)
    total_amount: float = 0.0
    count: int = 0
    as_of: datetime = Field(default_factory=datetime.now)


class MonthlySummary(BaseModel):
    """V4-Stub. Monats-Aggregat."""
    month: str  # 'YYYY-MM'
    total_in: float = 0.0
    total_out: float = 0.0
    net: float = 0.0
    open_items_count: int = 0
    open_items_total: float = 0.0
