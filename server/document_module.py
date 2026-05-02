import re
_re = re
# document_module.py
# document.module V1.1 — business.shiksha
# Extended: dunning, penalty_notice, multi-address matching, detection debug.
# Replaces document_module.py V1.

import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from document_models import (
    DocumentFieldCandidate,
    DocumentEntitySuggestion,
    DocumentAnalysisResponse,
    DetectionDebug,
    EntityAddress,
)


# ---------------------------------------------------------------------------
# DEMO ENTITY STUB — multi-address ready
# Replace get_known_entities() body with real DB query in V2.
# Shape is stable: List[dict] with id, name, addresses[]
# ---------------------------------------------------------------------------

DEMO_CUSTOMERS = [
    {
        "id": "cust_001",
        "name": "Müller GmbH",
        "addresses": [
            {"postal_code": "1010", "city": "Wien", "street": "Hauptstraße 12"},
        ],
    },
    {
        "id": "cust_002",
        "name": "Bauer & Partner",
        "addresses": [
            {"postal_code": "6900", "city": "Bregenz", "street": "Seestraße 5"},
        ],
    },
    {
        "id": "cust_lunchbox_001",
        "name": "Lunchbox Gastro GmbH",
        "aliases": ["Lunchbox", "lunchbox gastro"],   # trade names + short names
        "contacts": ["Knödler Thomas", "Thomas Knödler"],  # known persons
        "addresses": [
            {"postal_code": "6700", "city": "Bludenz", "street": "Werdenbergerstraße 38"},
            {"postal_code": "6700", "city": "Bludenz", "street": "Rathausgasse 1"},
            {"postal_code": "6700", "city": "Bludenz", "street": "Rathausgasse 1/3"},
            {"postal_code": "6700", "city": "Bludenz", "street": "Rungelinerstraße 22"},
        ],
    },
    {
        "id": "cust_003",
        "name": "Schmidt Consulting",
        "addresses": [
            {"postal_code": "5020", "city": "Salzburg", "street": "Linzergasse 3"},
        ],
    },
]

def get_known_entities(entity_type: str = "customer") -> List[dict]:
    """
    V1: demo stub.
    V2: replace body with DB query — return shape is stable.
    """
    if entity_type == "customer":
        return DEMO_CUSTOMERS
    return []


# ---------------------------------------------------------------------------
# 1. DOCUMENT TYPE DETECTION — with debug output
# ---------------------------------------------------------------------------
#
# Design principles:
# - dunning signals are checked BEFORE invoice — a dunning always has
#   invoice-like signals too (IBAN, Betrag), so dunning must win on specificity
# - penalty_notice signals are unique enough to stand alone
# - minimum 2 signals required for any type (prevents false positives)
# - ties resolved by specificity weight, not just count
# ---------------------------------------------------------------------------

# Each entry: keyword → weight (1 = normal, 2 = strong/specific signal)
TYPE_SIGNALS: dict = {

    "dunning": {
        "mahnung": 3,           # very specific — almost never in invoice
        "mahnschreiben": 3,
        "zahlungserinnerung": 3,
        "mahnkosten": 2,
        "mahngebühr": 2,
        "mahnstufe": 3,
        "beitragsrückstand": 2,
        "offener betrag": 2,
        "forderung": 1,
        "inkasso": 2,
        "dunning": 3,
        "reminder": 2,
        "overdue": 2,
        "zahlungsverzug": 2,
    },

    "penalty_notice": {
        "anonymverfügung": 3,
        "strafverfügung": 3,
        "verwaltungsstrafe": 3,
        "geldstrafe": 2,
        "verwaltungsübertretung": 3,
        "rechtsvorschrift": 2,
        "bezirkshauptmannschaft": 2,
        "magistrat": 1,
        "verkehrsübertretung": 2,
        "kennzeichen": 1,
        "lenker": 2,
        "tatzeit": 2,
        "stvo": 2,
        "vstg": 2,
        "penalty": 2,
        "fine": 1,
    },

    "invoice": {
        "rechnung": 3,
        "invoice": 3,
        "rechnungsnummer": 3,
        "invoice number": 3,
        "netto": 2,
        "nettosumme": 2,
        "brutto": 2,
        "bruttosumme": 3,
        "mwst": 1,
        "ust": 1,
        "mehrwertsteuer": 2,
        "steuer": 1,
        "iban": 1,
        "gesamtbetrag": 2,
        "total amount": 2,
        "zahlbar bis": 2,
        "due date": 2,
        # insurance invoice signals
        "erstbeitrag": 2,
        "beitragsart": 2,
        "folgebeitrag": 2,
        "praemie": 1,
        "polizzen-nr": 2,
        "polizze": 2,
        "beitrag": 1,
        # supplier / delivery invoice signals
        "beleg-nr": 2,
        "belegdatum": 2,
        "lieferant": 1,
    },

    "offer": {
        "angebot": 3,
        "offer": 2,
        "angebotsnummer": 3,
        "kostenvoranschlag": 3,
        "gültig bis": 2,
        "valid until": 2,
        "wir bieten": 2,
        "we offer": 2,
        "preisliste": 2,
        "angebotspreis": 3,
    },


    "delivery_note": {
        "lieferschein": 3,
        "delivery note": 3,
        "lieferschein-nr": 3,
        "lieferscheinnummer": 3,
        "liefermenge": 2,
        "gelieferte menge": 2,
        "lieferung": 2,
        "empfangsbestätigung": 2,
        "wareneingang": 2,
        "bestellnummer": 1,
        "artikel": 1,
    },

    "contract": {
        "vertrag": 3,
        "contract": 2,
        "vereinbarung": 2,
        "agreement": 2,
        "laufzeit": 2,
        "kündigung": 2,
        "termination": 2,
        "vertragspartner": 3,
        "contracting party": 2,
        "unterzeichnet": 1,
        "unterschrift": 1,
    },

    "note": {
        "notiz": 3,
        "memo": 2,
        "gesprächsnotiz": 3,
        "meeting notes": 3,
        "hinweis": 1,
        "anmerkung": 2,
        "protokoll": 1,
    },
}

def detect_document_type(raw_text: str) -> Tuple[str, DetectionDebug]:
    """
    Returns (document_type, DetectionDebug).
    document_type: invoice | dunning | penalty_notice | offer | contract | note | unknown
    DetectionDebug shows all scores and the reasoning — always populated.
    """
    text_lower = raw_text.lower()
    scores = {}
    triggered = {}  # type → list of matched keywords

    for doc_type, signals in TYPE_SIGNALS.items():
        total = 0
        hits = []
        for keyword, weight in signals.items():
            if keyword in text_lower:
                total += weight
                hits.append(f"{keyword}(+{weight})")
        scores[doc_type] = total
        triggered[doc_type] = hits

    # Sort by score descending
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_type, best_score = ranked[0]
    runner_up_type, runner_up_score = ranked[1] if len(ranked) > 1 else (None, 0)

    # Require minimum weighted score of 3 (e.g. one strong signal or 3 weak ones)
    MIN_SCORE = 3
    if best_score < MIN_SCORE:
        debug = DetectionDebug(
            scores=scores,
            winning_signals=[],
            runner_up=runner_up_type,
            runner_up_score=runner_up_score,
            decision_note=f"No type reached minimum score ({MIN_SCORE}). Best was '{best_type}' with {best_score}. → unknown",
        )
        return "unknown", debug

    decision_note = (
        f"'{best_type}' won with score {best_score} "
        f"(runner-up: '{runner_up_type}' with {runner_up_score}). "
        f"Signals: {', '.join(triggered[best_type])}"
    )

    debug = DetectionDebug(
        scores=scores,
        winning_signals=triggered[best_type],
        runner_up=runner_up_type,
        runner_up_score=runner_up_score,
        decision_note=decision_note,
    )

    return best_type, debug


# ---------------------------------------------------------------------------
# 2. FIELD EXTRACTION — per document type, candidates with confidence
# ---------------------------------------------------------------------------

# Shared extractors — reused across types

def _extract_date_near_label(text: str, labels: List[str], field_label: str) -> Optional[Tuple]:
    """Find a date that appears close to one of the given label keywords."""
    date_pat = r'(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{4}-\d{2}-\d{2})'
    for kw in labels:
        pattern = rf'{re.escape(kw)}[:\s]*{date_pat}'
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return (m.group(1).strip(), 0.88)
    # Fallback: first date in document, low confidence
    m = re.search(date_pat, text)
    if m:
        return (m.group(0).strip(), 0.45)
    return None

def _extract_customer_name(text: str) -> Optional[Tuple]:
    LEGAL_FULL = r'(?:GmbH|AG|KG|OHG|e\.K\.|GesnbR|V\.a\.G\.)'
    EXCLUDE = r'(?:bank|versicherung|sparkasse|raiffeisen|hypo|volksbank|bezirkshauptmannschaft|magistrat|iban|bic|uid)'
    NON_COMPANY = {
        'mahnung','rechnung','lieferschein','angebot','vertrag',
        'sehr','geehrte','geehrter','damen','herren','datum',
        'hagebau','baumarkt','markt','gartencenter','baustoffe',
        'anonymverfügung','firma','kunde','an','von','bestellung',
        'die','der','nachstehende','folgende','bitte','hiermit',
    }
    def _clean(val):
        val = val.strip()
        lm = _re.search(LEGAL_FULL + r'\s*$', val, _re.IGNORECASE)
        if not lm: return val
        words = val[:lm.end()].split()
        li = next((i for i,w in enumerate(words) if _re.match(LEGAL_FULL+r'$',w,_re.IGNORECASE)), None)
        if li is None: return val
        si = li
        for i in range(li-1,-1,-1):
            w=words[i]; wl=w.lower().rstrip('.,')
            if wl in NON_COMPANY: break
            if len(w)<=2 and w.islower(): break
            si=i
        return ' '.join(words[si:]).strip()

    t = _re.sub(r'\s+',' ',text).strip()

    m = _re.search(r'Firma\s+([A-ZÄÖÜ][a-zA-ZÄÖÜäöüß\s&\-\.]{2,50}?'+LEGAL_FULL+r')\b',t,_re.IGNORECASE)
    if m:
        val = _clean(m.group(1).strip().rstrip('.,'))
        if val and len(val)>=3 and not _re.search(EXCLUDE,val,_re.IGNORECASE):
            return (val,0.90)

    m = _re.search(r'(?:kunde|customer|auftraggeber|bill\s*to|rechnungsempfänger|rechnung\s*an)[:\s]+([^\n,]{3,60})',text,_re.IGNORECASE|_re.MULTILINE)
    if m:
        val=m.group(1).strip().split('\n')[0].rstrip('.,')
        if len(val)>=3: return (val,0.88)

    m = _re.search(r'(?:herr|frau)\s+([A-ZÄÖÜ][a-zA-ZÄÖÜäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zA-ZÄÖÜäöüß\-]+){0,2})',t,_re.IGNORECASE)
    if m:
        val=_re.split(r'\s+[a-zäöü]',m.group(1))[0].strip()
        if len(val)>=3: return (val,0.65)

    postal=_re.search(r'\b\d{4}\s+[A-ZÄÖÜ][a-z]',t)
    search_in=t[:postal.start()] if postal else t
    pat=r'([A-ZÄÖÜ][a-zA-ZÄÖÜäöüß\-\.]+(?:\s+[A-ZÄÖÜ&][a-zA-ZÄÖÜäöüß\-\.]*){0,4}\s+'+LEGAL_FULL+r')\b'
    all_m=[(m.group(1).strip(),m.start()) for m in _re.finditer(pat,search_in,_re.IGNORECASE)]
    valid=[(v,p) for v,p in all_m if not _re.search(EXCLUDE,v,_re.IGNORECASE)]
    if valid:
        val=_clean(valid[-1][0].rstrip('.,'))
        if val and len(val)>=3: return (val,0.72 if postal else 0.55)
    if all_m:
        val=_clean(all_m[-1][0].rstrip('.,'))
        if val and len(val)>=3: return (val,0.40)

    lines=text.split('\n')
    for i,line in enumerate(lines):
        if _re.search(r'\b\d{4}\s+[A-ZÄÖÜ][a-z]+',line):
            for j in range(max(0,i-3),i):
                c=lines[j].strip()
                if (len(c)>=3 and _re.match(r'[A-ZÄÖÜ]',c) and
                    not _re.search(r'\d{2,}',c) and
                    not _re.search(r'(?:gmbh|ag|kg|str\.|gasse|weg|platz)',c,_re.I) and
                    len(c.split())<=5): return (c,0.45)
    return None

def _extract_amount_total(text: str) -> Optional[Tuple]:
    """
    Extracts the total payable amount.
    Priority: bruttosumme > gesamtbetrag > gesamt > zu zahlen > endbetrag > fallback
    Tax fields (mwst, ust, steuer, vat) are NEVER used as amount_total.
    amount_tax is extracted separately by _extract_amount_tax.
    """
    # Step 1: identify and exclude tax-line positions to avoid picking MwSt as total
    TAX_LABELS = r'(?:mwst|mehrwertsteuer|ust|steuer|vat|tax|ust-betrag|steueranteil)'
    tax_positions = set()
    for m in _re.finditer(
        rf'{TAX_LABELS}[^\n]*?(\d+[.,]\d+)',
        text, _re.IGNORECASE
    ):
        tax_positions.add(m.start())

    # Get line numbers of tax-labeled lines for line-level exclusion
    lines_lower = text.lower().split('\n')
    tax_line_nums = set()
    for li, ln in enumerate(lines_lower):
        if _re.search(TAX_LABELS, ln):
            tax_line_nums.add(li)

    def _line_of(pos: int) -> int:
        return text[:pos].count('\n')

    def _find(pattern: str, conf: float) -> Optional[Tuple]:
        for m in _re.finditer(pattern, text, _re.IGNORECASE):
            # Reject only if the match is ON a tax-labeled line
            if _line_of(m.start()) in tax_line_nums:
                continue
            val = m.group(1).strip().replace(' ', '')
            if val:
                return (val, conf)
        return None

    # Priority order — most specific first
    result = (
        _find(r'bruttosumme[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.94) or
        _find(r'gesamt(?:betrag)?[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.90) or
        _find(r'total\s*(?:amount)?[:\s]*(?:eur\s*)?(\d[\d.,]+)', 0.88) or
        _find(r'zu\s*zahlen[:\s]*(?:eur\s*)?(\d[\d.,]+)', 0.86) or
        _find(r'endbetrag[:\s]*(?:eur\s*)?(\d[\d.,]+)', 0.85) or
        _find(r'offener?\s*betrag[:\s]*(?:eur\s*)?(\d[\d.,]+)', 0.85) or
        _find(r'geldstrafe[:\s]*(?:eur\s*)?(\d[\d.,]+)', 0.88)
    )
    if result:
        return result

    # Fallback: currency symbol or suffix — only if no tax overlap
    for m in _re.finditer(r'([€$]\s*[\d.,]+|[\d.,]+\s*(?:EUR|USD|CHF))', text, _re.IGNORECASE):
        if not any(abs(m.start() - tp) < 60 for tp in tax_positions):
            return (m.group(1).strip(), 0.55)

    return None



def _extract_amount_tax(text: str) -> Optional[Tuple]:
    """
    Extracts tax amount separately — never used as amount_total.
    """
    patterns = [
        (r'mwst\.?\s*gesamt[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.88),
        (r'mwst[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.82),
        (r'ust[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.80),
        (r'steuer(?:anteil|betrag)?[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.78),
        (r'vat[:\s|]*(?:eur\s*)?(\d[\d.,]+)', 0.80),
    ]
    for pattern, conf in patterns:
        m = _re.search(pattern, text, _re.IGNORECASE)
        if m:
            return (m.group(1).strip(), conf)
    return None
def _extract_currency(text: str) -> Optional[Tuple]:
    m = re.search(r'\b(EUR|USD|CHF|GBP)\b|([€$£])', text, re.IGNORECASE)
    if m:
        raw = (m.group(1) or m.group(2)).upper()
        normalized = {'€': 'EUR', '$': 'USD', '£': 'GBP'}.get(raw, raw)
        return (normalized, 0.95)
    return None

def _extract_iban(text: str) -> Optional[Tuple]:
    IBAN_LENGTHS = {
        'AT': 20, 'DE': 22, 'CH': 21, 'GB': 22, 'FR': 27,
        'IT': 27, 'ES': 24, 'NL': 18, 'BE': 16, 'LU': 20,
        'PL': 28, 'CZ': 24, 'SK': 24, 'HU': 28, 'RO': 24,
    }
    normalized = _re.sub(r"\n", " ", text)
    normalized = _re.sub(r"\s+", " ", normalized)

    def _validate(raw):
        cleaned = _re.sub(r"\s+", " ", raw.strip().upper())
        d = _re.sub(r"\s", "", cleaned)
        prefix = d[:2]
        exp = IBAN_LENGTHS.get(prefix, 0)
        if exp == 0:
            return cleaned, False, f"unknown prefix {prefix}"
        if len(d) == exp:
            return cleaned, True, None
        if len(d) < exp:
            return cleaned, False, f"truncated: {len(d)}/{exp} chars — manual check required"
        trimmed = d[:exp]
        spaced = " ".join(trimmed[i:i+4] for i in range(0, len(trimmed), 4))
        return spaced, True, "trimmed to correct length"

    patterns = [
        r"\b(AT\d{2}[\s\d]{15,18})\b",
        r"\b(DE\d{2}[\s\d]{18,22})\b",
        r"\b(CH\d{2}[\s\d]{17,19})\b",
        r"\b(GB\d{2}[A-Z\s\d]{15,20})\b",
        r"\b([A-Z]{2}\d{2}[\s\dA-Z]{10,30})\b",
    ]
    for pat in patterns:
        m = _re.search(pat, normalized, _re.IGNORECASE)
        if m:
            iban, valid, note = _validate(m.group(1))
            return (iban, 0.92, None) if valid else (iban, 0.35, note or "IBAN validation failed — manual check required")
    return None

def _extract_invoice_number(text: str) -> Optional[Tuple]:
    patterns = [
        (r'rechnungsnummer[:\s#]*([A-Z0-9\-\/\.]+)', 0.92),
        (r're(?:chnungs)?[.\-]?\s*nr\.?[:\s]*([A-Z0-9\-\/\.]+)', 0.88),
        (r'invoice\s*(?:number|no\.?|#)[:\s]*([A-Z0-9\-\/\.]+)', 0.90),
        (r'belegnr\.?[:\s]*([A-Z0-9\-\/\.]+)', 0.75),
    ]
    for pattern, conf in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return (m.group(1).strip(), conf)
    return None

def _extract_reference_number(text: str) -> Optional[Tuple]:
    """Generic reference/case number — used by dunning and penalty_notice."""
    patterns = [
        (r'zahl[:\s]+([A-Z0-9\-\/\.]+)', 0.88),
        (r'aktenzeichen[:\s]+([A-Z0-9\-\/\.]+)', 0.88),
        (r'kundennummer[:\s]+(\d+)', 0.85),
        (r'vertragskonto[:\s]+(\d+)', 0.85),
        (r'zahlungsreferenz[:\s]+(\d+)', 0.85),
        (r'polizzen[.\-]?nr\.?[:\s]+(\d+)', 0.88),
        (r'reference[:\s]+([A-Z0-9\-\/\.]+)', 0.80),
    ]
    for pattern, conf in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return (m.group(1).strip(), conf)
    return None

# --- dunning-specific ---

def _extract_reminder_level(text: str) -> Optional[Tuple]:
    patterns = [
        (r'mahnstufe[:\s]*([A-Z0-9\-]+)', 0.92),
        (r'(\d+)\.\s*mahnung', 0.85),
        (r'(?:erste|zweite|dritte|letzte)\s*mahnung', 0.80),
        (r'reminder\s*(?:level|no\.?)[:\s]*(\d+)', 0.80),
    ]
    for pattern, conf in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip() if m.lastindex and m.group(1) else m.group(0).strip()
            return (val, conf)
    return None

def _extract_referenced_invoice(text: str) -> Optional[Tuple]:
    patterns = [
        (r'(?:ursprüngliche|original)\s*rechnung[:\s#]*([A-Z0-9\-\/]+)', 0.85),
        (r're\.\s*nr\.?[:\s]*([A-Z0-9\-\/\.]+)', 0.80),
        (r'für\s*rechnung[:\s#]*([A-Z0-9\-\/]+)', 0.78),
    ]
    for pattern, conf in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return (m.group(1).strip(), conf)
    return None

# --- penalty_notice-specific ---

def _extract_vehicle_plate(text: str) -> Optional[Tuple]:
    # Austrian plate format: BZ-458FI, W-12345A, etc.
    patterns = [
        (r'kennzeichen[:\s]*([A-Z]{1,3}[\-\s]\d{1,5}[A-Z]{0,3})', 0.92),
        (r'\b([A-Z]{1,3}[\-]\d{2,5}[A-Z]{1,3})\b', 0.75),
    ]
    for pattern, conf in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return (m.group(1).strip().upper(), conf)
    return None

def _extract_authority_name(text: str) -> Optional[Tuple]:
    patterns = [
        (r'(bezirkshauptmannschaft\s+\w+)', 0.92),
        (r'(magistrat\s+\w+)', 0.88),
        (r'(landesverwaltungsgericht\s+\w+)', 0.90),
        (r'(finanzamt\s+\w+)', 0.88),
    ]
    for pattern, conf in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return (m.group(1).strip(), conf)
    return None

def _extract_incident_date(text: str) -> Optional[Tuple]:
    """Tatzeit / incident datetime — distinct from document date."""
    patterns = [
        r'tatzeit[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})',
        r'datum[/,]?zeit[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})',
        r'(?:am|tatdatum)[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})',
        r'(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})[,\s]*\d{1,2}:\d{2}\s*uhr',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return (m.group(1).strip(), 0.88)
    return None

def _extract_case_number(text: str) -> Optional[Tuple]:
    patterns = [
        (r'zahl[:\s]+([A-Z0-9\/\-\.]+)', 0.90),
        (r'geschäftszahl[:\s]+([A-Z0-9\/\-\.]+)', 0.90),
        (r'aktenzeichen[:\s]+([A-Z0-9\/\-\.]+)', 0.88),
    ]
    for pattern, conf in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return (m.group(1).strip(), conf)
    return None


# ---------------------------------------------------------------------------
# EXTRACTOR MAP — one entry per document type
# Each entry: list of (field_key, extractor_fn, confidence_note)
# ---------------------------------------------------------------------------

def _field(key: str, fn, note: Optional[str] = None):
    return (key, fn, note)

FIELD_EXTRACTORS = {

    "invoice": [
        _field("customer_name",   _extract_customer_name),
        _field("invoice_number",  _extract_invoice_number),
        _field("invoice_date",    lambda t: _extract_date_near_label(t,
            ["rechnungsdatum", "invoice date", "datum", "ausgestellt am"], "invoice_date")),
        _field("due_date",        lambda t: _extract_date_near_label(t,
            ["zahlbar bis", "fällig am", "due date", "zahlungsziel"], "due_date")),
        _field("amount_total",    _extract_amount_total),
        _field("amount_tax",      _extract_amount_tax),
        _field("currency",        _extract_currency),
        _field("iban",            _extract_iban),
    ],

    "dunning": [
        _field("customer_name",             _extract_customer_name),
        _field("document_date",             lambda t: _extract_date_near_label(t,
            ["datum", "bregenz", "wien", "graz", "bludenz", "linz"], "document_date"),
            "Date near city name — typical for Austrian formal letters"),
        _field("referenced_invoice_number", _extract_referenced_invoice),
        _field("due_date",                  lambda t: _extract_date_near_label(t,
            ["zahlbar bis", "fällig", "fällig bis", "bis spätestens", "due", "einzahlen bis"], "due_date")),
        _field("reminder_level",            _extract_reminder_level),
        _field("amount_due",                _extract_amount_total),
        _field("currency",                  _extract_currency),
        _field("reference_number",          _extract_reference_number),
        _field("iban",                      _extract_iban),
    ],

    "penalty_notice": [
        _field("customer_name",   _extract_customer_name),
        _field("authority_name",  _extract_authority_name),
        _field("case_number",     _extract_case_number),
        _field("document_date",   lambda t: _extract_date_near_label(t,
            ["datum", "bludenz", "wien", "bregenz", "ausgestellt"], "document_date")),
        _field("incident_date",   _extract_incident_date),
        _field("vehicle_plate",   _extract_vehicle_plate,
            "Kennzeichen — custom field, not in base schema"),
        _field("amount_due",      _extract_amount_total),
        _field("currency",        _extract_currency),
    ],


    "delivery_note": [
        _field("customer_name",   _extract_customer_name),
        _field("document_date",   lambda t: _extract_date_near_label(t,
            ["lieferdatum", "datum", "date"], "document_date")),
        _field("reference_number", _extract_reference_number),
        _field("amount_total",    _extract_amount_total),
        _field("currency",        _extract_currency),
    ],

    "offer": [
        _field("customer_name",  _extract_customer_name),
        _field("offer_number",   _extract_invoice_number),
        _field("offer_date",     lambda t: _extract_date_near_label(t,
            ["angebotsdatum", "datum", "ausgestellt am"], "offer_date")),
        _field("valid_until",    lambda t: _extract_date_near_label(t,
            ["gültig bis", "valid until", "angebot gültig"], "valid_until")),
        _field("amount_total",   _extract_amount_total),
        _field("currency",       _extract_currency),
    ],

    "contract": [
        _field("customer_name",  _extract_customer_name),
        _field("contract_date",  lambda t: _extract_date_near_label(t,
            ["vertragsdatum", "datum", "unterzeichnet am"], "contract_date")),
        _field("reference_number", _extract_reference_number),
    ],

    "note": [
        _field("customer_name",  _extract_customer_name),
        _field("document_date",  lambda t: _extract_date_near_label(t,
            ["datum", "date"], "document_date")),
    ],

    "unknown": [
        _field("customer_name",  _extract_customer_name),
        _field("amount_due",     _extract_amount_total),
        _field("reference_number", _extract_reference_number),
        _field("document_date",  lambda t: _extract_date_near_label(t,
            ["datum", "date"], "document_date")),
    ],
}

def extract_field_candidates(
    raw_text: str,
    document_type: str,
    source_quality: str = "text",
) -> List[DocumentFieldCandidate]:
    """
    Runs all extractors for the given document type.
    Applies source_quality penalty: image_scan → -0.05 on all confidences.
    All values are candidates — never facts.
    """
    extractors = FIELD_EXTRACTORS.get(document_type, FIELD_EXTRACTORS["unknown"])
    quality_penalty = -0.05 if source_quality == "image_scan" else 0.0
    candidates = []

    for entry in extractors:
        field_key, extractor_fn, *rest = entry
        note = rest[0] if rest else None

        result = extractor_fn(raw_text)
        if result:
            if len(result) == 3:
                value, confidence, extractor_note = result
            else:
                value, confidence = result
                extractor_note = None
            adjusted = round(max(0.0, confidence + quality_penalty), 2)
            # extractor_note overrides the static field note
            final_note = extractor_note if extractor_note else note
            candidates.append(DocumentFieldCandidate(
                field_key=field_key,
                field_value=value,
                confidence=adjusted,
                confidence_note=final_note,
            ))

    return candidates


# ---------------------------------------------------------------------------
# 3. ENTITY MATCHING — name-primary, address-secondary
# ---------------------------------------------------------------------------
#
# Design:
# - name_score is the primary signal (0.0–1.0)
# - address_score is additive bonus (max +0.10 to final confidence)
# - An address match alone never produces a suggestion
# - Multiple addresses per entity are all checked
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    return re.sub(r'[\s,./]+', ' ', s.lower()).strip()

def _name_similarity(a: str, b: str) -> float:
    """Returns 0.0–1.0. Exact > substring > token overlap."""
    na, nb = _normalize(a), _normalize(b)
    if na == nb:
        return 1.0
    if nb in na or na in nb:
        return 0.80
    tokens_a = set(na.split())
    tokens_b = set(nb.split())
    overlap = tokens_a & tokens_b
    if not overlap:
        return 0.0
    return round(len(overlap) / max(len(tokens_a), len(tokens_b)), 2) * 0.75

def _address_similarity(extracted_raw: Optional[str], entity_addresses: List[dict]) -> Tuple[float, str]:
    """
    Returns (score 0.0–1.0, note).
    Checks all known addresses for the entity.
    """
    if not extracted_raw:
        return 0.0, "no address extracted"

    norm_extracted = _normalize(extracted_raw)

    for addr in entity_addresses:
        # Build normalized comparison string from structured fields
        addr_parts = [
            addr.get("street", ""),
            addr.get("postal_code", ""),
            addr.get("city", ""),
        ]
        norm_addr = _normalize(" ".join(p for p in addr_parts if p))

        # Token overlap between extracted address fragment and known address
        tokens_e = set(norm_extracted.split())
        tokens_a = set(norm_addr.split())
        overlap = tokens_e & tokens_a

        if len(overlap) >= 2:
            score = round(len(overlap) / max(len(tokens_e), len(tokens_a)), 2)
            label = addr.get("street", addr.get("city", "?"))
            note = f"address match: '{label}' (overlap: {sorted(overlap)})"
            return min(score, 1.0), note

    return 0.0, "no address match found"

def _extract_address_fragment(field_candidates: List[DocumentFieldCandidate]) -> Optional[str]:
    """Try to find any address-like text in candidates or return None."""
    for c in field_candidates:
        if c.field_key in ("customer_address", "address"):
            return c.field_value
    return None

def suggest_customer_link(
    field_candidates: List[DocumentFieldCandidate],
    known_entities: Optional[List[dict]] = None,
    raw_text: Optional[str] = None,
) -> DocumentEntitySuggestion:
    """
    Name-primary matching with address bonus.
    Returns DocumentEntitySuggestion — operator must always confirm.
    """
    if known_entities is None:
        known_entities = get_known_entities("customer")

    name_candidate = next(
        (f for f in field_candidates if f.field_key == "customer_name"), None
    )

    if not name_candidate:
        return DocumentEntitySuggestion(
            match_basis=None,
            confidence=0.0,
            review_required=True,
        )

    # Try to find address fragment from raw text for address bonus
    address_fragment = None
    if raw_text:
        # Look for postal code + city pattern in raw text
        m = re.search(r'(\d{4}\s+[A-ZÄÖÜa-zäöüß]+)', raw_text)
        if m:
            address_fragment = m.group(1)

    best_entity = None
    best_name_score = 0.0
    best_addr_score = 0.0
    best_addr_note = ""

    for entity in known_entities:
        # Check primary name
        name_score = _name_similarity(name_candidate.field_value, entity["name"])

        # Also check aliases (trade names, short names) — V1.1
        for alias in entity.get("aliases", []):
            alias_score = _name_similarity(name_candidate.field_value, alias)
            if alias_score > name_score:
                name_score = alias_score * 0.92  # slight penalty vs exact name match

        # Also check known contacts (persons linked to this entity) — V1.1
        for contact in entity.get("contacts", []):
            contact_score = _name_similarity(name_candidate.field_value, contact)
            if contact_score > name_score:
                name_score = contact_score * 0.85  # person match = lower confidence than entity name

        if name_score < 0.30:
            continue  # not worth checking address

        addr_score, addr_note = _address_similarity(
            address_fragment,
            entity.get("addresses", []),
        )

        # Name is primary — address can only add bonus, not compensate
        if name_score > best_name_score or (
            name_score == best_name_score and addr_score > best_addr_score
        ):
            best_entity = entity
            best_name_score = name_score
            best_addr_score = addr_score
            best_addr_note = addr_note

    if not best_entity or best_name_score < 0.30:
        return DocumentEntitySuggestion(
            match_basis="name",
            name_score=0.0,
            address_score=0.0,
            confidence=0.0,
            review_required=True,
        )

    # Address adds max +0.10 bonus
    addr_bonus = round(min(best_addr_score * 0.10, 0.10), 2)

    # Dampen by name candidate's own confidence
    raw_confidence = best_name_score + addr_bonus
    final_confidence = round(raw_confidence * name_candidate.confidence, 2)
    final_confidence = min(final_confidence, 0.97)  # cap — operator always verifies

    match_basis = "name+address" if best_addr_score > 0 else "name"

    return DocumentEntitySuggestion(
        target_type="customer",
        suggested_entity_id=best_entity["id"],
        suggested_entity_name=best_entity["name"],
        match_basis=match_basis,
        name_score=round(best_name_score, 2),
        address_score=round(best_addr_score, 2),
        confidence=final_confidence,
        address_note=best_addr_note if best_addr_score > 0 else None,
        review_required=True,
    )


# ---------------------------------------------------------------------------
# 4. BUILD FULL ANALYSIS
# ---------------------------------------------------------------------------

def build_document_analysis(
    raw_text: str,
    edition: str = "business.shiksha",
    source_type: str = "text",
) -> DocumentAnalysisResponse:
    """
    Full pipeline: detect → extract → suggest.
    No side effects. No DB writes. Returns DocumentAnalysisResponse.
    """
    document_id = str(uuid.uuid4())
    source_quality = source_type  # "text" | "image_scan" | "pdf"

    document_type, detection_debug = detect_document_type(raw_text)

    field_candidates = extract_field_candidates(
        raw_text, document_type, source_quality
    )

    entity_suggestion = suggest_customer_link(
        field_candidates,
        raw_text=raw_text,
    )

    return DocumentAnalysisResponse(
        document_id=document_id,
        edition=edition,
        detected_document_type=document_type,
        source_quality=source_quality,
        extracted_fields=field_candidates,
        entity_suggestion=entity_suggestion,
        review_required=True,
        status="analyzed",
        created_at=datetime.now(timezone.utc),
        detection_debug=detection_debug,
    )

# DB override for get_known_entities
def get_known_entities(entity_type="customer"):
    try:
        import sqlalchemy as _sa
        from database import engine
        with engine.connect() as conn:
            rows = conn.execute(_sa.text("SELECT id,name,aliases,contacts,addresses FROM customers ORDER BY name")).fetchall()
            return [{"id":r[0],"name":r[1],"aliases":r[2] or [],"contacts":r[3] or [],"addresses":r[4] or []} for r in rows]
    except Exception as e:
        print(f"DB error: {e}"); return []
