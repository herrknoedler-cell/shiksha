# accounting_module.py
# SHIKSHA accounting.module — Kernlogik Stufe 1
# Version: 1.0
#
# Verantwortung:
# - Ledger-Einträge aus Dokumenten erstellen
# - Offene Posten verwalten
# - Zahlungen bestätigen
# - Monatszusammenfassung
#
# Nicht hier: automatische Buchungen, Steuerberater-Export (Stufe 2)
# Nicht hier: Editions-Logik — das entscheidet der Orchestrator

import uuid
from datetime import datetime, timezone, date
from typing import Optional, List

import sqlalchemy as sa

from accounting_models import (
    LedgerEntry,
    LedgerEntryCreate,
    LedgerFromDocumentRequest,
    PaymentConfirmRequest,
    PaymentConfirmResponse,
    PaymentRecord,
    OpenItem,
    OpenItemsResponse,
    MonthlySummary,
)

# ---------------------------------------------------------------------------
# DB CONNECTION
# ---------------------------------------------------------------------------

from database import engine as _shared_engine

def _engine():
    return _shared_engine


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_amount(value: str) -> Optional[float]:
    """Konvertiert Betragsstring wie '116,11' oder '1.234,56' zu float."""
    if not value:
        return None
    try:
        cleaned = value.replace(".", "").replace(",", ".")
        return float(cleaned)
    except Exception:
        return None


def _entry_type_from_doc(document_type: str) -> str:
    """
    Bestimmt entry_type aus Dokumenttyp.
    Eingangsrechnungen, Mahnungen, Strafen = expense
    """
    income_types = {"income", "sale"}
    if document_type in income_types:
        return "income"
    return "expense"


def _days_overdue(due_date_str: Optional[str]) -> Optional[int]:
    """Gibt Anzahl überfälliger Tage zurück, oder None wenn nicht fällig."""
    if not due_date_str:
        return None
    try:
        # Unterstützt DD.MM.YYYY und YYYY-MM-DD
        if "." in due_date_str:
            parts = due_date_str.strip().split(".")
            d = date(int(parts[2]), int(parts[1]), int(parts[0]))
        else:
            d = date.fromisoformat(due_date_str[:10])
        delta = (date.today() - d).days
        return delta if delta > 0 else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 1. LEDGER ENTRY ERSTELLEN — aus Dokument
# ---------------------------------------------------------------------------

def create_entry_from_document(request: LedgerFromDocumentRequest) -> LedgerEntry:
    """
    Liest Dokument + Field Candidates aus DB.
    Erstellt Ledger-Eintrag — Operator hat Dokument bereits bestätigt.
    """
    engine = _engine()
    now = _now()

    with engine.connect() as conn:
        # Dokument holen
        doc = conn.execute(
            sa.text("SELECT id, document_type, status FROM documents WHERE id = :id"),
            {"id": request.document_id}
        ).fetchone()

        if not doc:
            raise ValueError(f"Dokument nicht gefunden: {request.document_id}")

        # Felder holen
        fields = conn.execute(
            sa.text("""
                SELECT field_key, field_value, confidence
                FROM document_field_candidates
                WHERE document_id = :id AND confidence >= 0.50
                ORDER BY confidence DESC
            """),
            {"id": request.document_id}
        ).fetchall()

    field_map = {f.field_key: f.field_value for f in fields}

    # Betrag ermitteln
    amount_raw = (
        field_map.get("amount_total") or
        field_map.get("amount_due") or
        field_map.get("amount")
    )
    amount = _parse_amount(amount_raw) if amount_raw else None

    # Steuer
    tax_raw = field_map.get("amount_tax")
    tax_amount = _parse_amount(tax_raw) if tax_raw else None

    # Fälligkeit
    due_date = (
        field_map.get("due_date") or
        field_map.get("document_date") or
        field_map.get("invoice_date")
    )

    # Währung
    currency = field_map.get("currency", "EUR")

    # Entry-Typ
    entry_type = request.entry_type or _entry_type_from_doc(doc.document_type)

    entry_id = str(uuid.uuid4())

    with _engine().begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO ledger_entries
                (id, document_id, entity_id, entity_type, entry_type,
                 amount, currency, tax_amount, due_date, status, note, created_at, updated_at)
            VALUES
                (:id, :document_id, :entity_id, :entity_type, :entry_type,
                 :amount, :currency, :tax_amount, :due_date, 'open', :note, :created_at, :updated_at)
        """), {
            "id": entry_id,
            "document_id": request.document_id,
            "entity_id": request.entity_id,
            "entity_type": "customer",
            "entry_type": entry_type,
            "amount": amount,
            "currency": currency,
            "tax_amount": tax_amount,
            "due_date": due_date,
            "note": request.note,
            "created_at": now,
            "updated_at": now,
        })

    return LedgerEntry(
        id=entry_id,
        document_id=request.document_id,
        entity_id=request.entity_id,
        entity_type="customer",
        entry_type=entry_type,
        amount=amount or 0.0,
        currency=currency,
        tax_amount=tax_amount,
        due_date=due_date,
        status="open",
        note=request.note,
        created_at=now,
    )


# ---------------------------------------------------------------------------
# 2. OFFENE POSTEN
# ---------------------------------------------------------------------------

def get_open_items(
    entity_id: Optional[str] = None,
    entry_type: Optional[str] = None,
) -> OpenItemsResponse:
    """
    Gibt offene + überfällige Posten zurück.
    Optional gefiltert nach entity_id und entry_type.
    """
    engine = _engine()

    query = """
        SELECT
            le.id, le.document_id, le.entity_id, le.entity_type,
            le.entry_type, le.amount, le.currency, le.due_date,
            le.status, le.created_at,
            c.name AS entity_name
        FROM ledger_entries le
        LEFT JOIN customers c ON c.id = le.entity_id
        WHERE le.status IN ('open', 'overdue')
    """
    params = {}

    if entity_id:
        query += " AND le.entity_id = :entity_id"
        params["entity_id"] = entity_id

    if entry_type:
        query += " AND le.entry_type = :entry_type"
        params["entry_type"] = entry_type

    query += " ORDER BY le.created_at DESC"

    with engine.connect() as conn:
        rows = conn.execute(sa.text(query), params).fetchall()

    items = []
    total = 0.0
    currency = "EUR"

    for r in rows:
        days_od = _days_overdue(r.due_date)

        # Auto-update status zu overdue wenn fällig
        if days_od and r.status == "open":
            with _engine().begin() as conn:
                conn.execute(sa.text("""
                    UPDATE ledger_entries SET status = 'overdue', updated_at = :now
                    WHERE id = :id
                """), {"id": r.id, "now": _now()})
            status = "overdue"
        else:
            status = r.status

        amount = float(r.amount) if r.amount else 0.0
        total += amount
        currency = r.currency or "EUR"

        items.append(OpenItem(
            ledger_entry_id=r.id,
            document_id=r.document_id,
            entity_id=r.entity_id,
            entity_name=r.entity_name,
            entry_type=r.entry_type,
            amount=amount,
            currency=currency,
            due_date=r.due_date,
            status=status,
            days_overdue=days_od,
            created_at=r.created_at,
        ))

    return OpenItemsResponse(
        count=len(items),
        total_amount=round(total, 2),
        currency=currency,
        entity_id=entity_id,
        items=items,
    )


# ---------------------------------------------------------------------------
# 3. ZAHLUNG BESTÄTIGEN
# ---------------------------------------------------------------------------

def confirm_payment(request: PaymentConfirmRequest) -> PaymentConfirmResponse:
    """
    Bestätigt Zahlung — setzt Ledger-Entry auf 'paid'.
    Operator-Entscheidung, nie automatisch.
    """
    engine = _engine()
    now = _now()
    payment_id = str(uuid.uuid4())

    with engine.connect() as conn:
        entry = conn.execute(
            sa.text("SELECT id, amount, status FROM ledger_entries WHERE id = :id"),
            {"id": request.ledger_entry_id}
        ).fetchone()

    if not entry:
        raise ValueError(f"Ledger-Eintrag nicht gefunden: {request.ledger_entry_id}")

    with _engine().begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO payment_records
                (id, ledger_entry_id, paid_amount, paid_date, payment_note, confirmed_by, created_at)
            VALUES
                (:id, :ledger_entry_id, :paid_amount, :paid_date, :payment_note, 'operator', :created_at)
        """), {
            "id": payment_id,
            "ledger_entry_id": request.ledger_entry_id,
            "paid_amount": request.paid_amount,
            "paid_date": request.paid_date,
            "payment_note": request.payment_note,
            "created_at": now,
        })

        conn.execute(sa.text("""
            UPDATE ledger_entries SET status = 'paid', updated_at = :now
            WHERE id = :id
        """), {"id": request.ledger_entry_id, "now": now})

    return PaymentConfirmResponse(
        success=True,
        ledger_entry_id=request.ledger_entry_id,
        new_status="paid",
        payment=PaymentRecord(
            id=payment_id,
            ledger_entry_id=request.ledger_entry_id,
            paid_amount=request.paid_amount,
            paid_date=request.paid_date,
            payment_note=request.payment_note,
            confirmed_by="operator",
            created_at=now,
        )
    )


# ---------------------------------------------------------------------------
# 4. MONATSZUSAMMENFASSUNG
# ---------------------------------------------------------------------------

def get_monthly_summary(year: int, month: int) -> MonthlySummary:
    """
    Gibt Zusammenfassung für einen Monat zurück.
    Basiert auf created_at der Ledger-Entries.
    """
    engine = _engine()

    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, document_id, entity_id, entity_type, entry_type,
                   amount, currency, tax_amount, due_date, status, note, created_at
            FROM ledger_entries
            WHERE EXTRACT(YEAR FROM created_at) = :year
              AND EXTRACT(MONTH FROM created_at) = :month
            ORDER BY created_at DESC
        """), {"year": year, "month": month}).fetchall()

    entries = []
    total_expenses = 0.0
    total_income = 0.0
    total_tax = 0.0

    for r in rows:
        amount = float(r.amount) if r.amount else 0.0
        tax = float(r.tax_amount) if r.tax_amount else 0.0

        if r.entry_type == "expense":
            total_expenses += amount
        elif r.entry_type == "income":
            total_income += amount
        total_tax += tax

        entries.append(LedgerEntry(
            id=r.id,
            document_id=r.document_id,
            entity_id=r.entity_id,
            entity_type=r.entity_type,
            entry_type=r.entry_type,
            amount=amount,
            currency=r.currency or "EUR",
            tax_amount=tax if tax else None,
            due_date=r.due_date,
            status=r.status,
            note=r.note,
            created_at=r.created_at,
        ))

    return MonthlySummary(
        year=year,
        month=month,
        total_expenses=round(total_expenses, 2),
        total_income=round(total_income, 2),
        total_tax=round(total_tax, 2),
        entry_count=len(entries),
        balance=round(total_income - total_expenses, 2),
        entries=entries,
    )
