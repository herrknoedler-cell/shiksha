"""
extractor_extensions.py
SHIKSHA · Document-Module Erweiterung

Erweitert FIELD_EXTRACTORS["invoice"] um:
  - invoice_number_v2  (kennt "Beleg-Nr.", "Belegnummer", "Auftrags-Nr.", Spalten-Layout)
  - iban               (war definiert, aber nicht registriert)
  - vat_amount         (Mwst-Betrag, USt-Betrag, Mehrwertsteuer)
  - vat_rate           (10%, 20% etc.)
  - uid_number         (ATU12345678, DE123456789)
  - supplier_name      (Lieferant am Briefkopf, wenn Lunchbox/Lichtquelle Empfänger)
  - due_date_strict    (nur wenn explizit "Fällig"/"Zahlbar bis" steht — kein Fallback)
  - amount_total_table (Tabellen-Footer-Heuristik: letzte größte Zahl bei Brutto/Gesamt/Total)

Wird in main.py importiert NACH `from document_module import ...`.
Patch ist additiv: bestehende Extractoren bleiben unverändert.

Stand: 28.04.2026
"""
from __future__ import annotations
import re
from typing import Optional, Tuple, List

import document_module as dm


# ============================================================
# 1. EXTRACTORS
# ============================================================

def _extract_invoice_number_v2(text: str) -> Optional[Tuple]:
    """
    Erweiterte Patterns inkl. österreichischer Variante "Beleg-Nr."
    + Spalten-Layout (Label \n Wert).
    """
    patterns = [
        # Standard
        (r'rechnungsnummer[:\s#]*([A-Z0-9][\w\-\/\.]{2,30})', 0.92),
        (r're(?:chnungs)?[.\-]?\s*nr\.?[:\s]*([A-Z0-9][\w\-\/\.]{2,30})', 0.88),
        (r'invoice\s*(?:number|no\.?|#)[:\s]*([A-Z0-9][\w\-\/\.]{2,30})', 0.90),
        # Österreichische Varianten — Beleg-Nr. MIT Bindestrich
        (r'beleg[\.\-\s]*nr\.?[:\s]+([A-Z0-9][\w\-\/\.]{2,30})', 0.86),
        (r'belegnummer[:\s]+([A-Z0-9][\w\-\/\.]{2,30})', 0.86),
        (r'auftrags[.\-]?\s*nr\.?[:\s]*([A-Z0-9][\w\-\/\.]{2,30})', 0.78),
        # Spalten-Layout: Label, dann nächste Zeile mit Wert
        (r'beleg[.\-\s]*nr\.?\s*\n\s*([A-Z0-9][\w\-\/\.]{2,30})', 0.84),
        (r'belegnummer\s*\n\s*([A-Z0-9][\w\-\/\.]{2,30})', 0.84),
        (r'rechnungsnummer\s*\n\s*([A-Z0-9][\w\-\/\.]{2,30})', 0.86),
    ]
    for pattern, conf in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip().rstrip('.,;:')
            # Filter: keine reinen Zahlen unter 4 Zeichen, keine Wörter
            if len(val) >= 3 and not val.lower() in {'kunde','firma','datum','seite','belegdatum','lieferdatum','uid','uid-nummer','bestellreferenz','kopie','sachbearbeiter','zahlung','rechnung','total','summe','netto','brutto','mwst','ust'}:
                return (val, conf)
    return None


def _extract_vat_amount(text: str) -> Optional[Tuple]:
    """Mwst-Betrag, USt-Betrag, Mehrwertsteuer (Geldbetrag)."""
    patterns = [
        (r'mwst[.\-\s]*betrag[:\s]*(?:eur\s*)?(\d+[.,]\d+)', 0.92),
        (r'ust[.\-\s]*betrag[:\s]*(?:eur\s*)?(\d+[.,]\d+)', 0.92),
        (r'umsatzsteuer[:\s]*(?:eur\s*)?(\d+[.,]\d+)', 0.88),
        (r'mehrwertsteuer[:\s]*(?:eur\s*)?(\d+[.,]\d+)', 0.88),
        (r'\bvat\b[:\s]*(?:eur\s*)?(\d+[.,]\d+)', 0.82),
        # Tabellen-Heuristik: Spalte "Mwst-Betrag" oben, dann letzter Zahlenwert in Spalte
        (r'mwst[.\-\s]*betrag\s*\n(?:.*\n){0,4}\s*(\d+[.,]\d+)', 0.70),
    ]
    for pat, conf in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            val = m.group(1).replace(' ', '')
            return (val, conf)
    return None


def _extract_vat_rate(text: str) -> Optional[Tuple]:
    """MwSt/USt-Satz (z.B. 10%, 20%)."""
    patterns = [
        (r'mwst\.?\s*[:\-]?\s*(\d{1,2})\s*%', 0.90),
        (r'ust\s*[:\-]?\s*(\d{1,2})\s*%', 0.90),
        (r'mehrwertsteuer\s+(\d{1,2})\s*%', 0.88),
        (r'(\d{1,2})\s*%\s*mwst', 0.86),
        (r'(\d{1,2})\s*%\s*ust', 0.86),
    ]
    for pat, conf in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            v = m.group(1)
            try:
                vi = int(v)
                # Plausible MwSt-Sätze AT/DE
                if vi in (0, 5, 7, 10, 13, 19, 20):
                    return (f'{vi}%', conf)
            except ValueError:
                pass
    return None


def _extract_uid_number(text: str) -> Optional[Tuple]:
    """UID-Nummer (AT, DE, etc.)."""
    patterns = [
        (r'\b(ATU\d{8})\b', 0.95),
        (r'\b(DE\d{9})\b', 0.94),
        (r'uid[\.\-\s]*(?:nummer|nr\.?)?[:\s]*([A-Z]{2}\d{6,12})', 0.90),
        (r'ust[\.\-\s]*id(?:\s*nr\.?)?[:\s]*([A-Z]{2}\d{6,12})', 0.90),
        (r'umsatzsteuer[\.\-\s]*id(?:entifikations)?[\.\-\s]*nr\.?[:\s]*([A-Z]{2}\d{6,12})', 0.92),
    ]
    for pat, conf in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return (m.group(1).upper().strip(), conf)
    return None


def _extract_supplier_name(text: str) -> Optional[Tuple]:
    """
    Lieferant — sucht im Briefkopf (erste 15 Zeilen) nach Firma mit GmbH/AG-Suffix.
    Strikt: KG nur am Ende und nach mind. 2 Wörtern; "kg" als Mengenangabe ausgeschlossen.
    """
    LEGAL_STRICT = r'(?:GmbH|AG|OHG|e\.K\.|GesnbR|V\.a\.G\.|SE)'  # KG separat behandelt
    EXCLUDE = r'(?:lunchbox|lichtquelle|inselwellen|allweglehen|knödler|knodler)'
    NON_NAMES = {
        'rechnung','mahnung','lieferschein','angebot','kunde','firma',
        'kg','st','stk','stück','liter','ltr','ml','gramm','seite','art','nr',
        'datum','beleg','zahlung','total','summe','netto','brutto','mwst','ust',
    }
    head = '\n'.join(text.split('\n')[:15])

    # Variante 1: GmbH/AG/SE/OHG (strikte Rechtsformen)
    pat = r'([A-ZÄÖÜ][a-zA-ZÄÖÜäöüß\s&\-\.]{4,55}\s+' + LEGAL_STRICT + r')\b'
    for m in re.finditer(pat, head):
        val = m.group(1).strip().rstrip('.,;:')
        if re.search(EXCLUDE, val, re.IGNORECASE):
            continue
        first_word = val.split()[0].lower().rstrip('.,')
        if first_word in NON_NAMES:
            continue
        if len(val) >= 6 and len(val.split()) >= 2:
            return (val, 0.82)

    # Variante 2: KG nur wenn KG am Ende UND mindestens 2 Wörter davor UND
    # davor steht kein Großbuchstabe-isoliertes "KG" (Kilogramm-Pattern wie "1 KG")
    pat_kg = r'(?:^|\n)\s*([A-ZÄÖÜ][a-zA-ZÄÖÜäöüß\-\.]{2,30}(?:\s+[A-ZÄÖÜ][a-zA-ZÄÖÜäöüß\-\.&]{2,30}){1,4})\s+KG\b'
    for m in re.finditer(pat_kg, head, re.MULTILINE):
        val = m.group(1).strip() + " KG"
        # vorausgehende Zeile prüfen: keine Mengenangabe direkt davor
        if re.search(r'\d+\s*(?:ST|STK|stk)?\s*$', m.string[:m.start(1)]):
            continue
        if re.search(EXCLUDE, val, re.IGNORECASE):
            continue
        first_word = val.split()[0].lower().rstrip('.,')
        if first_word in NON_NAMES:
            continue
        if len(val.split()) >= 3:
            return (val, 0.72)

    return None


def _extract_due_date_strict(text: str) -> Optional[Tuple]:
    """
    Strikte due_date — KEIN Fallback auf erstes Datum.
    Nur wenn explizit "Fällig", "Zahlbar bis", "Zahlungsziel" da steht.
    """
    date_pat = r'(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{4}-\d{2}-\d{2})'
    labels = [
        (r'fällig\s*(?:am|bis)', 0.94),
        (r'fälligkeit(?:sdatum)?', 0.92),
        (r'zahlbar\s*bis', 0.92),
        (r'zahlungsziel', 0.88),
        (r'zahlungsfrist', 0.88),
        (r'zu\s*zahlen\s*bis', 0.90),
        (r'due\s*date', 0.90),
        (r'payment\s*due', 0.90),
    ]
    for label_pat, conf in labels:
        m = re.search(rf'{label_pat}[:\s]*{date_pat}', text, re.IGNORECASE)
        if m:
            return (m.group(1).strip(), conf)
    return None


def _extract_amount_total_table(text: str) -> Optional[Tuple]:
    """
    Bessere amount_total für Tabellen-Layout:
    Sucht in den letzten 15 Zeilen nach Brutto/Gesamt/Total + nächster Zahl.
    Fängt Eurogast/Hagebau/etc. ab, wo das Total am Ende steht.
    """
    # nur die letzten 15 Zeilen anschauen — dort steht typischerweise das Total
    lines = text.split('\n')
    tail = '\n'.join(lines[-25:])

    patterns = [
        (r'bruttosumme[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.94),
        (r'rechnungsbetrag[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.92),
        (r'gesamtsumme[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.92),
        (r'gesamtbetrag[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.92),
        (r'endbetrag[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.90),
        (r'zu\s*zahlen[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.90),
        (r'rechnungssumme[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.90),
        (r'gesamt(?:\s*brutto)?[:\s|]+(?:eur\s*)?(\d[\d.,]+)', 0.85),
        (r'total[:\s|]+(?:eur\s*)?(\d[\d.,]+)', 0.83),
    ]
    # zuerst im Tail
    for pat, conf in patterns:
        m = re.search(pat, tail, re.IGNORECASE)
        if m:
            return (m.group(1).strip().replace(' ', ''), conf)
    # dann im ganzen Text
    for pat, conf in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            return (m.group(1).strip().replace(' ', ''), max(0.0, conf - 0.05))
    return None


# ============================================================
# 2. REGISTRIERUNG IN FIELD_EXTRACTORS
# ============================================================

# Neue/bessere Felder für invoice
EXTENDED_FIELDS = [
    # Replacements (überschreiben bestehende)
    ("invoice_number", _extract_invoice_number_v2, "extended pattern"),
    ("amount_total",   _extract_amount_total_table, "table-aware"),
    # Neue Felder (ergänzend)
    ("iban",           dm._extract_iban,            None),
    ("vat_amount",     _extract_vat_amount,         None),
    ("vat_rate",       _extract_vat_rate,           None),
    # uid_number deaktiviert: in den meisten Eurogast/Hagebau-Rechnungen steht nur das Label,
    # kein Wert. Manuell pflegen, wenn Lieferanten-Stammdaten kommen.
    # ("uid_number",     _extract_uid_number,         None),
    ("supplier_name",  _extract_supplier_name,      None),
    ("due_date_strict",_extract_due_date_strict,    None),
]

# Felder, die bestehende ersetzen statt ergänzen
REPLACE_KEYS = {"invoice_number", "amount_total"}


def _patch_field_extractors():
    """
    Patch FIELD_EXTRACTORS["invoice"] und ähnliche Document-Types.
    - Ersetzt invoice_number + amount_total mit besseren Versionen
    - Ergänzt iban, vat_amount, vat_rate, uid_number, supplier_name, due_date_strict
    """
    target_types = ("invoice", "dunning", "reminder")
    fe = getattr(dm, "FIELD_EXTRACTORS", None)
    if fe is None:
        print("[extractor_extensions] WARNUNG: FIELD_EXTRACTORS nicht gefunden!")
        return

    patched = []
    for doc_type in target_types:
        if doc_type not in fe:
            continue
        existing = fe[doc_type]
        existing_keys = {entry[0] for entry in existing}
        new_list = list(existing)

        for entry in EXTENDED_FIELDS:
            key = entry[0]
            if key in REPLACE_KEYS and key in existing_keys:
                # Ersetzen
                for i, ent in enumerate(new_list):
                    if ent[0] == key:
                        new_list[i] = entry
                        break
            elif key not in existing_keys:
                # Ergänzen
                new_list.append(entry)

        fe[doc_type] = new_list
        patched.append(doc_type)

    print(f"[extractor_extensions] FIELD_EXTRACTORS gepatcht für: {patched}")
    print(f"[extractor_extensions] Neue Felder: iban, vat_amount, vat_rate, uid_number, supplier_name, due_date_strict")
    print(f"[extractor_extensions] Verbesserte Felder: invoice_number, amount_total")


# Direkt beim Import patchen
_patch_field_extractors()


# ============================================================
# 3. RE-EXTRACT HELPER (für bestehende Documents)
# ============================================================

def re_extract_document(raw_text: str, document_type: str = "invoice") -> List[dict]:
    """
    Läuft alle Extractoren neu auf einem bestehenden raw_text.
    Liefert Liste von dicts: [{field_key, field_value, confidence}, ...]
    """
    candidates = dm.extract_field_candidates(raw_text, document_type, "pdf")
    return [
        {
            "field_key": c.field_key,
            "field_value": c.field_value,
            "confidence": c.confidence,
        }
        for c in candidates
    ]
