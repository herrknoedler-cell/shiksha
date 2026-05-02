"""
SHIKSHA · Accounting Smoke-Test V1
Stand: 25.04.2026

Lädt das fiktive Lunchbox-Bank-Statement, baut fiktive offene Rechnungen,
führt das Matching aus und zeigt das Ergebnis sprachfähig an.

Aufruf:
    cd outputs/accounting/test_data
    python3 smoke_test_accounting.py
"""

import sys
from datetime import date, datetime
from pathlib import Path

# Pfade zu accounting-Server-Code
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from accounting_models import (
    AccountingInvoice, AccountingStateResponse,
    BankTransaction, MatchProposal,
)
from accounting_orchestrator import (
    proposals_for_all_unmatched,
    proposals_for_transaction,
    build_state_summary,
    build_aging_report,
    build_accounting_state,
    score_match,
    THRESHOLD_HIGH_CONFIDENCE,
    THRESHOLD_MEDIUM_CONFIDENCE,
    LANGUAGE_TEMPLATES,
)
from bank_statement_parser import parse_csv


# ---------------------------------------------------------------------------
# 1. Fiktive offene Rechnungen — passend zu den Bank-Buchungen
# ---------------------------------------------------------------------------

OPEN_INVOICES_LUNCHBOX = [
    # Eingangsrechnungen (Lunchbox/Lichtquelle/Inselwellen schuldet)
    AccountingInvoice(
        id="d94204c2",
        document_type="invoice",
        direction="incoming",
        customer_name="Eurogast Grissemann GmbH",
        invoice_number="d94204c2",
        invoice_date=date(2026, 4, 18),
        due_date=date(2026, 5, 2),
        amount_total=106.40,
        outstanding_amount=106.40,
        iban="AT41 2070 1234 5678 9012",
        accounting_status="open",
    ),
    AccountingInvoice(
        id="67cb9021",
        document_type="dunning",
        direction="incoming",
        customer_name="illwerke vkw AG",
        invoice_number="67cb9021",
        invoice_date=date(2026, 3, 15),
        due_date=date(2026, 4, 15),
        amount_total=116.11,
        outstanding_amount=116.11,
        iban="AT44 5800 0000 1192 0011",
        accounting_status="overdue",
    ),
    AccountingInvoice(
        id="b4383d84",
        document_type="invoice",
        direction="incoming",
        customer_name="Bezirkshauptmannschaft Bludenz",
        invoice_number="BZ-458FI",
        invoice_date=date(2026, 3, 28),
        due_date=date(2026, 4, 28),
        amount_total=60.00,
        outstanding_amount=60.00,
        iban="AT58 5800 0000 4321 0987",
        accounting_status="open",
    ),
    AccountingInvoice(
        id="21284fce",
        document_type="dunning",
        direction="incoming",
        customer_name="Vorarlberger Landes-Versicherung V.a.G.",
        invoice_number="21284fce",
        invoice_date=date(2026, 3, 20),
        due_date=date(2026, 4, 17),
        amount_total=75.22,
        outstanding_amount=75.22,
        iban="AT75 5800 0000 1192 8161",
        accounting_status="overdue",
    ),
    AccountingInvoice(
        id="arag_2026_998877",
        document_type="dunning",
        direction="incoming",
        customer_name="ARAG Sportversicherung",
        invoice_number="SP-2026-998877",
        invoice_date=date(2026, 2, 28),
        due_date=date(2026, 5, 9),
        amount_total=1488.93,
        outstanding_amount=1488.93,
        iban="DE12 3007 0024 0987 6543",
        accounting_status="reminder_1",
    ),
    AccountingInvoice(
        id="baeck_april",
        document_type="invoice",
        direction="incoming",
        customer_name="Bäckerei Lechner",
        invoice_number="2026-04-Sammel",
        invoice_date=date(2026, 4, 30),
        due_date=date(2026, 5, 14),
        amount_total=87.40,
        outstanding_amount=87.40,
        iban="DE45 7105 0000 0123 4567",
        accounting_status="open",
    ),
    AccountingInvoice(
        id="berchtesgaden_kurtaxe_maerz",
        document_type="invoice",
        direction="incoming",
        customer_name="Markt Berchtesgaden",
        invoice_number="KT-Cmp-014",
        invoice_date=date(2026, 4, 14),
        due_date=date(2026, 5, 2),
        amount_total=482.40,
        outstanding_amount=482.40,
        iban="DE87 7105 0000 0123 4500",
        accounting_status="open",
    ),
    AccountingInvoice(
        id="vkb_2026_447723",
        document_type="invoice",
        direction="incoming",
        customer_name="Bayerische Versicherungskammer",
        invoice_number="2026-VKB-09-117",
        invoice_date=date(2026, 1, 5),
        due_date=date(2026, 1, 31),
        amount_total=535.02,
        outstanding_amount=535.02,
        iban="AT12 1100 0001 2345 6789",
        accounting_status="overdue",
    ),
    AccountingInvoice(
        id="gemeinde_sylt_strandzonen",
        document_type="invoice",
        direction="incoming",
        customer_name="Gemeinde Sylt — Ordnungsamt",
        invoice_number="OA-Sylt/2026-Surfschulen/0034",
        invoice_date=date(2026, 4, 14),
        due_date=date(2026, 4, 30),
        amount_total=1984.00,
        outstanding_amount=1984.00,
        iban="DE45 2175 0000 0987 6543",
        accounting_status="open",
    ),

    # Ausgangsrechnungen (Lichtquelle/Inselwellen erwartet Geld)
    AccountingInvoice(
        id="lichtquelle_2026_0341",
        document_type="invoice",
        direction="outgoing",
        customer_name="Anna Fischer",
        invoice_number="2026-0341",
        invoice_date=date(2026, 3, 8),
        due_date=date(2026, 3, 22),
        amount_total=180.00,
        outstanding_amount=180.00,
        iban="AT26 2011 1000 5550 6678",
        accounting_status="overdue",
    ),
    AccountingInvoice(
        id="lichtquelle_2026_0298",
        document_type="invoice",
        direction="outgoing",
        customer_name="Werner Hofbauer",
        invoice_number="2026-0298",
        invoice_date=date(2026, 3, 12),
        due_date=date(2026, 3, 26),
        amount_total=110.00,
        outstanding_amount=110.00,
        iban="AT26 2011 1000 5550 6678",
        accounting_status="reminder_1",
    ),
    AccountingInvoice(
        id="inselwellen_R_2026_1142",
        document_type="invoice",
        direction="outgoing",
        customer_name="Sophie Bauer",
        invoice_number="R-2026-1142",
        invoice_date=date(2026, 4, 22),
        due_date=date(2026, 5, 6),
        amount_total=110.00,
        outstanding_amount=110.00,
        iban="DE89 2175 0000 0123 4567",
        accounting_status="open",
    ),
    AccountingInvoice(
        id="allweglehen_R_2026_0341",
        document_type="invoice",
        direction="outgoing",
        customer_name="Familie Schmidt",
        invoice_number="R-2026-0341",
        invoice_date=date(2026, 4, 12),
        due_date=date(2026, 4, 26),
        amount_total=386.00,  # nur Anzahlung 30%
        outstanding_amount=386.00,
        iban="DE99 7105 0000 0987 6543",
        accounting_status="open",
    ),
]


# Hack: AccountingInvoice hat kein direction_explicit_note Feld — stripped ich raus.
# Die direction_explicit_note ist nur für Lesbarkeit hier.


# ---------------------------------------------------------------------------
# 2. Smoke-Test Workflow
# ---------------------------------------------------------------------------

def main():
    print("=" * 76)
    print(" SHIKSHA · Accounting Smoke-Test")
    print("=" * 76)
    print()

    # 1. CSV-Statement parsen
    csv_path = Path(__file__).parent / "lunchbox_demo_statement.csv"
    csv_content = csv_path.read_text(encoding="utf-8")

    transactions, statement = parse_csv(
        content=csv_content,
        iban_account="AT75 5800 0000 1192 8161",  # Hypo-Konto Lunchbox
        profile_key="hypo_vorarlberg",
    )

    print(f"📄 Bank-Statement importiert: {statement.file_name}")
    print(f"   Format: {statement.file_format} · Profil: {statement.bank_profile}")
    print(f"   Buchungen: {statement.transactions_count} · Periode: {statement.period_from} bis {statement.period_to}")
    print(f"   Parse-Fehler: {statement.parse_errors}")
    print()

    # 2. Match-Vorschläge generieren
    proposals_by_tx = proposals_for_all_unmatched(transactions, OPEN_INVOICES_LUNCHBOX)

    print(f"🔍 Match-Engine läuft gegen {len(OPEN_INVOICES_LUNCHBOX)} offene Rechnungen ...")
    print()

    high_count = 0
    medium_count = 0
    low_count = 0
    no_match_count = 0

    for tx in transactions:
        proposals = proposals_by_tx.get(tx.id, [])

        # Direction-Marker
        sign = "+" if tx.amount > 0 else "−"
        amount_abs = abs(tx.amount)
        direction_label = "EIN" if tx.amount > 0 else "AUS"

        print(f"  {direction_label} {sign}{amount_abs:7.2f}€  {tx.value_date}  {(tx.counterparty_name or '?')[:40]}")
        if tx.purpose:
            print(f"      → {tx.purpose[:80]}")

        if not proposals:
            print(f"      ⚪ Kein Match")
            no_match_count += 1
        else:
            top = proposals[0]
            tier = "🟢 HIGH" if top.score >= THRESHOLD_HIGH_CONFIDENCE else "🟡 MED" if top.score >= THRESHOLD_MEDIUM_CONFIDENCE else "🔴 LOW"
            template = LANGUAGE_TEMPLATES.get(top.language_key or "", {})
            action = template.get("action", "?")
            try:
                rendered = action.format(**top.language_params)
            except (KeyError, IndexError):
                rendered = action

            print(f"      {tier} (score={top.score})  {rendered}")
            print(f"      Bewertung: {top.score_breakdown.model_dump() if top.score_breakdown else '—'}")

            if top.score >= THRESHOLD_HIGH_CONFIDENCE:
                high_count += 1
            elif top.score >= THRESHOLD_MEDIUM_CONFIDENCE:
                medium_count += 1
            else:
                low_count += 1

            if len(proposals) > 1:
                print(f"      Weitere Kandidaten: {len(proposals) - 1}")
        print()

    # 3. Gesamtbild
    print("=" * 76)
    print(" 📊 Smoke-Test-Ergebnis")
    print("=" * 76)
    print(f"  🟢 Hohe Confidence (sicherer Match):    {high_count}")
    print(f"  🟡 Mittlere Confidence (Operator prüft): {medium_count}")
    print(f"  🔴 Niedrige Confidence (manueller Match):{low_count}")
    print(f"  ⚪ Kein Match (Operator entscheidet):    {no_match_count}")
    print()

    # 4. Aging-Report
    print("=" * 76)
    print(" 📅 Aging-Report (Eingangsrechnungen — Lunchbox schuldet)")
    print("=" * 76)
    aging = build_aging_report(OPEN_INVOICES_LUNCHBOX, direction="incoming")
    for bucket in aging.buckets:
        print(f"  {bucket.label:9s}  {bucket.count} Posten  {bucket.total_amount:8.2f}€  ({bucket.description})")
    print(f"\n  Total offen: {aging.total_open_amount:.2f}€")
    if aging.earliest_due_date:
        print(f"  Älteste Fälligkeit: {aging.earliest_due_date}")
    print()

    # 5. State-Summary
    print("=" * 76)
    print(" 💬 Sprachfähige Tageszusammenfassung")
    print("=" * 76)

    # Mock: ein paar Pending-Proposals als Liste sammeln
    all_proposals = []
    for proposals in proposals_by_tx.values():
        if proposals:
            all_proposals.append(proposals[0])

    today_tx = [tx for tx in transactions if tx.value_date == date(2026, 4, 22)]
    summary = build_state_summary(OPEN_INVOICES_LUNCHBOX, all_proposals, today_tx, today=date(2026, 4, 22))
    print()
    print(f"  „{summary}\"")
    print()


if __name__ == "__main__":
    main()
