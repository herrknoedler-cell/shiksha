"""
SHIKSHA · Bank-Statement-Parser V1.1
Stand: 26.04.2026

V1.1 ergänzt:
- UTF-16 / UTF-8-BOM Auto-Detection
- George-Profil (Erste Bank / Sparkasse Bregenz)
- IBAN-Auto-Detection aus 'Eigene IBAN' Spalte
"""

import csv
import hashlib
import io
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Optional

from accounting_models import (
    BankTransaction, StatementFormat, StatementImport, TransactionType,
)


# ---------------------------------------------------------------------------
# 1. CSV-Profile
# ---------------------------------------------------------------------------

CSV_PROFILES: dict[str, dict] = {
    "george_at": {
        "delimiter": ",",
        "encoding_hint": "utf-16",
        "columns": {
            "own_iban": "Eigene IBAN",
            "booking_date": "Buchungsdatum",
            "value_date": "Buchungsdatum",
            "amount": "Betrag",
            "currency": "Währung",
            "purpose": "Buchungs-Details",
            "counterparty_iban": "Partner IBAN",
            "counterparty_name": "Partnername",
            "counterparty_bic": "BIC/SWIFT",
            "bank_reference": None,
        },
        "date_format": "%d.%m.%Y",
        "amount_decimal": ",",
    },
    "hypo_vorarlberg": {
        "delimiter": ";",
        "encoding_hint": "iso-8859-1",
        "columns": {
            "booking_date": "Buchungstag",
            "value_date": "Valutadatum",
            "amount": "Betrag",
            "currency": "Währung",
            "purpose": "Buchungstext",
            "counterparty_iban": "IBAN Zahlungspartner",
            "counterparty_name": "Zahlungspartner",
            "bank_reference": "Buchungsnummer",
        },
        "date_format": "%d.%m.%Y",
        "amount_decimal": ",",
    },
    "sparkasse_bgl": {
        "delimiter": ";",
        "encoding_hint": "iso-8859-1",
        "columns": {
            "booking_date": "Buchungstag",
            "value_date": "Valutadatum",
            "amount": "Betrag",
            "currency": "Währung",
            "purpose": "Verwendungszweck",
            "counterparty_iban": "Empfänger Konto",
            "counterparty_name": "Auftraggeber/Empfänger",
            "bank_reference": "Buchungsnummer",
        },
        "date_format": "%d.%m.%y",
        "amount_decimal": ",",
    },
    "generic_csv": {
        "delimiter": ";",
        "encoding_hint": "utf-8",
        "columns": {
            "booking_date": "booking_date",
            "value_date": "value_date",
            "amount": "amount",
            "currency": "currency",
            "purpose": "purpose",
            "counterparty_iban": "counterparty_iban",
            "counterparty_name": "counterparty_name",
            "bank_reference": "bank_reference",
        },
        "date_format": "%Y-%m-%d",
        "amount_decimal": ".",
    },
}


# ---------------------------------------------------------------------------
# 2. Encoding Auto-Detection
# ---------------------------------------------------------------------------

def decode_smart(content_bytes: bytes) -> str:
    """Erkennt BOM + decodet entsprechend."""
    if content_bytes.startswith(b'\xff\xfe'):
        return content_bytes.decode('utf-16-le')
    if content_bytes.startswith(b'\xfe\xff'):
        return content_bytes.decode('utf-16-be')
    if content_bytes.startswith(b'\xef\xbb\xbf'):
        return content_bytes.decode('utf-8-sig')
    # Fallback-Kaskade
    for enc in ('utf-8', 'iso-8859-1', 'cp1252'):
        try:
            return content_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return content_bytes.decode('iso-8859-1', errors='ignore')


# ---------------------------------------------------------------------------
# 3. Profile Detection
# ---------------------------------------------------------------------------

def detect_csv_profile(content: str) -> str:
    """Erkennt automatisch das CSV-Profil aus dem Header."""
    first_line = content.split('\n', 1)[0].lower().strip().lstrip('\ufeff')

    if "eigene iban" in first_line and "partnername" in first_line and "buchungs-details" in first_line:
        return "george_at"
    if "buchungstag" in first_line and "valutadatum" in first_line and "iban zahlungspartner" in first_line:
        return "hypo_vorarlberg"
    if "buchungstag" in first_line and "verwendungszweck" in first_line:
        return "sparkasse_bgl"
    return "generic_csv"


# ---------------------------------------------------------------------------
# 4. Amount Parser
# ---------------------------------------------------------------------------

def parse_german_amount(value: str, decimal: str = ",") -> Optional[float]:
    if not value:
        return None
    cleaned = str(value).strip().strip('"')
    is_negative = cleaned.startswith("-") or cleaned.endswith("-")
    cleaned = cleaned.replace("-", "").replace("+", "").strip()
    if decimal == ",":
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        amount = float(cleaned)
        return -amount if is_negative else amount
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 5. CSV-Parser
# ---------------------------------------------------------------------------

def parse_csv(
    content,                        # str ODER bytes
    iban_account: Optional[str] = None,
    profile_key: Optional[str] = None,
) -> tuple[list[BankTransaction], StatementImport]:
    """Parst CSV mit Auto-Detection von Encoding + Profil + IBAN."""

    # 1) Bytes → String mit Encoding-Detection
    if isinstance(content, bytes):
        original_bytes = content
        content = decode_smart(content)
    else:
        original_bytes = content.encode('utf-8', errors='ignore')

    # 2) Profil erkennen, falls nicht angegeben
    if profile_key is None:
        profile_key = detect_csv_profile(content)
    profile = CSV_PROFILES.get(profile_key, CSV_PROFILES["generic_csv"])

    delimiter = profile["delimiter"]
    cols = profile["columns"]
    date_fmt = profile["date_format"]
    amount_decimal = profile["amount_decimal"]

    # 3) BOM strippen + parsen
    content = content.lstrip('\ufeff')
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter, quotechar='"')

    transactions: list[BankTransaction] = []
    parse_errors = 0
    period_from = None
    period_to = None
    detected_iban = iban_account

    for row in reader:
        try:
            # Auto-IBAN aus 'Eigene IBAN' Spalte
            if not detected_iban and cols.get("own_iban"):
                own = (row.get(cols["own_iban"], "") or "").strip().replace(" ", "")
                if own:
                    detected_iban = own

            value_date_str = (row.get(cols["value_date"], "") or "").strip()
            amount_str = (row.get(cols["amount"], "") or "").strip()
            if not value_date_str or not amount_str:
                continue

            value_date = datetime.strptime(value_date_str, date_fmt).date()
            booking_date_str = (row.get(cols.get("booking_date", ""), "") or "").strip()
            booking_date = (
                datetime.strptime(booking_date_str, date_fmt).date()
                if booking_date_str else value_date
            )

            amount = parse_german_amount(amount_str, decimal=amount_decimal)
            if amount is None:
                parse_errors += 1
                continue

            cp_iban_raw = (row.get(cols.get("counterparty_iban", ""), "") or "").strip()
            cp_iban = cp_iban_raw.replace(" ", "") if cp_iban_raw else None

            tx = BankTransaction(
                id=f"tx_{uuid.uuid4().hex[:12]}",
                iban_account=detected_iban or "UNKNOWN",
                booking_date=booking_date,
                value_date=value_date,
                amount=amount,
                currency=(row.get(cols.get("currency", "currency"), "") or "EUR").strip() or "EUR",
                counterparty_name=(row.get(cols.get("counterparty_name", ""), "") or "").strip() or None,
                counterparty_iban=cp_iban,
                counterparty_bic=(row.get(cols.get("counterparty_bic", ""), "") or "").strip() or None,
                purpose=(row.get(cols.get("purpose", ""), "") or "").strip() or None,
                bank_reference=(row.get(cols.get("bank_reference", "") or "", "") or "").strip() or None if cols.get("bank_reference") else None,
                transaction_type=infer_transaction_type(row, amount),
                raw_record=dict(row),
            )
            transactions.append(tx)

            if period_from is None or value_date < period_from:
                period_from = value_date
            if period_to is None or value_date > period_to:
                period_to = value_date

        except Exception:
            parse_errors += 1

    statement = StatementImport(
        id=f"si_{uuid.uuid4().hex[:12]}",
        file_name="upload.csv",
        file_format="csv",
        bank_profile=profile_key,
        iban_account=detected_iban or "UNKNOWN",
        period_from=period_from,
        period_to=period_to,
        transactions_count=len(transactions),
        new_count=len(transactions),
        parse_errors=parse_errors,
        file_hash=hashlib.sha256(original_bytes).hexdigest(),
    )

    return transactions, statement


def infer_transaction_type(row: dict, amount: float) -> TransactionType:
    text = " ".join(str(v) for v in row.values()).lower()
    if "dauerauftrag" in text or "standing" in text:
        return "standing_order"
    if "lastschrift" in text or "sepa-debit" in text:
        return "sepa_debit"
    if "überweisung" in text or "george-überweisung" in text or "ueberweisung" in text:
        return "sepa_credit"
    if "pos " in text or "kartenzahlung" in text or "card" in text:
        return "card"
    if "bargeld" in text or "barauszahlung" in text or "cash" in text:
        return "cash"
    if "gebühr" in text or "fee" in text or "spesen" in text or "sollzinsen" in text:
        return "fee"
    return "other"


# ---------------------------------------------------------------------------
# 6. CAMT.053 + MT940 (unverändert von V1)
# ---------------------------------------------------------------------------

def parse_camt053(content, iban_account: Optional[str] = None):
    if isinstance(content, bytes):
        content = decode_smart(content)
    root = ET.fromstring(content)
    if root.tag.startswith("{"):
        ns_uri = root.tag.split("}")[0].strip("{")
        ns = {"ns": ns_uri}
    else:
        ns = {"ns": ""}

    transactions: list[BankTransaction] = []
    period_from = None
    period_to = None

    if not iban_account:
        iban_node = root.find(".//ns:Stmt/ns:Acct/ns:Id/ns:IBAN", ns) or root.find(".//ns:Acct/ns:Id/ns:IBAN", ns)
        if iban_node is not None and iban_node.text:
            iban_account = iban_node.text.strip()
    iban_account = iban_account or "UNKNOWN"

    for entry in root.findall(".//ns:Ntry", ns):
        try:
            amount_node = entry.find("ns:Amt", ns)
            cdt_dbt_node = entry.find("ns:CdtDbtInd", ns)
            value_date_node = entry.find("ns:ValDt/ns:Dt", ns)
            booking_date_node = entry.find("ns:BookgDt/ns:Dt", ns)
            details = entry.find("ns:NtryDtls/ns:TxDtls", ns)
            if amount_node is None or value_date_node is None:
                continue
            amount = float(amount_node.text or 0)
            currency = amount_node.get("Ccy", "EUR")
            if cdt_dbt_node is not None and cdt_dbt_node.text == "DBIT":
                amount = -amount
            value_date = datetime.strptime(value_date_node.text, "%Y-%m-%d").date()
            booking_date = datetime.strptime(booking_date_node.text, "%Y-%m-%d").date() if booking_date_node is not None and booking_date_node.text else value_date

            counterparty_name = None
            counterparty_iban = None
            purpose = None
            bank_reference = None
            if details is not None:
                cp_name_node = details.find(".//ns:RltdPties/ns:Cdtr/ns:Nm", ns) or details.find(".//ns:RltdPties/ns:Dbtr/ns:Nm", ns)
                if cp_name_node is not None:
                    counterparty_name = cp_name_node.text
                cp_iban_node = details.find(".//ns:RltdPties/ns:CdtrAcct/ns:Id/ns:IBAN", ns) or details.find(".//ns:RltdPties/ns:DbtrAcct/ns:Id/ns:IBAN", ns)
                if cp_iban_node is not None:
                    counterparty_iban = cp_iban_node.text
                rmt_inf = details.find("ns:RmtInf/ns:Ustrd", ns)
                if rmt_inf is not None:
                    purpose = rmt_inf.text
                ref_node = details.find("ns:Refs/ns:AcctSvcrRef", ns) or details.find("ns:Refs/ns:EndToEndId", ns)
                if ref_node is not None:
                    bank_reference = ref_node.text

            tx = BankTransaction(
                id=f"tx_{uuid.uuid4().hex[:12]}",
                iban_account=iban_account,
                booking_date=booking_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
                counterparty_name=counterparty_name,
                counterparty_iban=counterparty_iban,
                purpose=purpose,
                bank_reference=bank_reference,
                transaction_type="sepa_credit" if amount > 0 else "sepa_debit",
                raw_record={"camt053": True},
            )
            transactions.append(tx)
            if period_from is None or value_date < period_from:
                period_from = value_date
            if period_to is None or value_date > period_to:
                period_to = value_date
        except Exception:
            continue

    statement = StatementImport(
        id=f"si_{uuid.uuid4().hex[:12]}", file_name="upload.xml", file_format="camt053",
        iban_account=iban_account, period_from=period_from, period_to=period_to,
        transactions_count=len(transactions), new_count=len(transactions),
        file_hash=hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest(),
    )
    return transactions, statement


def parse_mt940(content, iban_account: Optional[str] = None):
    if isinstance(content, bytes):
        content = decode_smart(content)
    transactions: list[BankTransaction] = []
    period_from = None
    period_to = None
    tag_61 = re.compile(r":61:(\d{6})(\d{4})?(C|D|RC|RD)([A-Z]?)?(\d+,\d{2})N?[A-Z]{3}", re.MULTILINE)
    tag_86 = re.compile(r":86:(.+?)(?=:\d{2}[A-Z]?:|$)", re.DOTALL)
    for block in re.split(r"(?=:61:)", content):
        m61 = tag_61.search(block)
        if not m61:
            continue
        try:
            v = m61.group(1)
            cdt_dbt = m61.group(3)
            amt = parse_german_amount(m61.group(5), decimal=",") or 0
            if cdt_dbt in ("D", "RD"):
                amt = -amt
            vd = date(2000+int(v[0:2]), int(v[2:4]), int(v[4:6]))
            m86 = tag_86.search(block)
            purpose = (m86.group(1).replace("\n"," ").strip() if m86 else None)
            transactions.append(BankTransaction(
                id=f"tx_{uuid.uuid4().hex[:12]}",
                iban_account=iban_account or "UNKNOWN",
                booking_date=vd, value_date=vd, amount=amt, currency="EUR",
                purpose=purpose,
                transaction_type="sepa_credit" if amt > 0 else "sepa_debit",
                raw_record={"mt940": True},
            ))
            if period_from is None or vd < period_from: period_from = vd
            if period_to is None or vd > period_to: period_to = vd
        except Exception:
            continue
    statement = StatementImport(
        id=f"si_{uuid.uuid4().hex[:12]}", file_name="upload.mt940", file_format="mt940",
        iban_account=iban_account or "UNKNOWN", period_from=period_from, period_to=period_to,
        transactions_count=len(transactions), new_count=len(transactions),
        file_hash=hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest(),
    )
    return transactions, statement


# ---------------------------------------------------------------------------
# 7. Public API + Duplikat-Erkennung
# ---------------------------------------------------------------------------

def parse_statement(content, file_format: StatementFormat, iban_account: str, bank_profile: Optional[str] = None):
    if file_format == "csv":
        return parse_csv(content, iban_account, bank_profile)
    elif file_format == "camt053":
        return parse_camt053(content, iban_account)
    elif file_format == "mt940":
        return parse_mt940(content, iban_account)
    raise ValueError(f"Unbekanntes Format: {file_format}")


def detect_duplicates(new_transactions, existing_bank_references):
    new_only, duplicates = [], []
    for tx in new_transactions:
        key = tx.bank_reference or _fingerprint(tx)
        if key in existing_bank_references:
            duplicates.append(tx)
        else:
            new_only.append(tx)
            existing_bank_references.add(key)
    return new_only, duplicates


def _fingerprint(tx):
    parts = [tx.iban_account or "", tx.value_date.isoformat() if tx.value_date else "",
             f"{tx.amount:.2f}", (tx.purpose or "")[:40]]
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]


__all__ = [
    "CSV_PROFILES", "decode_smart", "detect_csv_profile",
    "parse_csv", "parse_camt053", "parse_mt940", "parse_statement",
    "detect_duplicates",
]
