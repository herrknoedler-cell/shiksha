"""Identity-OCR — Tesseract-Wrapper + MRZ-Parser + Whitelist + Hash.

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §3.3 (mrz_parsed whitelist),
§7.1 (Hash-Strategie + normalize_doc_number).

Layering:
  run_ocr(bytes) -> (text, confidence)
  parse_mrz(text) -> dict | None        (raw MRZ-Felder inkl. doc_number)
  filter_mrz_to_whitelist(parsed, allowed) -> dict
                                        (verworfen: alles ausser allowed)
  normalize_doc_number(raw) -> str      (trim + inner-whitespace + upper)
  hash_doc_number(normalized, tenant_salt, hex_length) -> str

Caller (Router) ist verantwortlich:
  1. run_ocr → text + confidence
  2. parse_mrz → raw dict (oder None)
  3. doc_number aus raw separat hashen + identity_persons.doc_number_hash setzen
  4. filter_mrz_to_whitelist → safe dict für identity_documents.mrz_parsed
     (raw doc_number landet hier NIE drin)
"""
from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from typing import Any

from shiksha_engine.settings import get_settings

log = logging.getLogger("shiksha.identity.ocr")


class OCRError(RuntimeError):
    """Tesseract konnte nicht ausgeführt werden."""


class OCRTimeoutError(OCRError):
    """Tesseract-Lauf > tesseract_timeout_seconds."""


# ============================================================ Tesseract


def run_ocr(image_bytes: bytes) -> tuple[str, float]:
    """Tesseract-Wrapper. Liefert (text, confidence_estimate).

    Confidence ist eine Heuristik basierend auf Wortzahl (≥30 ≈ klarer
    Scan, <10 ≈ Pixelmatsch). Reicht für Mitarbeiter-Triage und Audit-
    Reporting; nicht für automatische Verifikations-Entscheidungen.
    """
    settings = get_settings()
    timeout = settings.tesseract_timeout_seconds
    languages = settings.tesseract_languages

    try:
        result = subprocess.run(
            ["tesseract", "-", "-", "-l", languages, "--psm", "6"],
            input=image_bytes,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise OCRTimeoutError(f"tesseract timeout > {timeout}s") from exc
    except FileNotFoundError as exc:
        raise OCRError("tesseract binary nicht im PATH") from exc

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")[:200]
        raise OCRError(f"tesseract returncode={result.returncode}: {stderr}")

    text = result.stdout.decode("utf-8", errors="replace")
    words = re.findall(r"\w{3,}", text)
    confidence = min(100.0, len(words) * 3.33)  # 30 Wörter → 100%
    return text, round(confidence, 2)


# ============================================================ MRZ-Parser


# TD1 (Personalausweis): 3 Zeilen à 30 Zeichen
# TD3 (Reisepass):       2 Zeilen à 44 Zeichen
_TD1_LEN = 30
_TD3_LEN = 44


def _find_mrz_lines(text: str) -> list[str]:
    """Extrahiert MRZ-Zeilen (mindestens 2 mit < als Filler) aus OCR-Output."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return [ln for ln in lines if "<<" in ln and len(ln) >= 28]


def _yymmdd_to_iso(yymmdd: str) -> str | None:
    """'940115' → '1994-01-15'. Heuristik: YY < 50 → 20xx, sonst 19xx."""
    if not yymmdd or len(yymmdd) != 6 or not yymmdd.isdigit():
        return None
    yy, mm, dd = yymmdd[:2], yymmdd[2:4], yymmdd[4:6]
    full_year = 2000 + int(yy) if int(yy) < 50 else 1900 + int(yy)
    try:
        return f"{full_year:04d}-{int(mm):02d}-{int(dd):02d}"
    except ValueError:
        return None


def _split_name(field: str) -> tuple[str | None, str | None]:
    """'MUSTERMANN<<MAX<HEINRICH' → ('MUSTERMANN', 'MAX HEINRICH')."""
    parts = field.split("<<", 1)
    if len(parts) < 2:
        return field.replace("<", " ").strip() or None, None
    surname = parts[0].replace("<", " ").strip() or None
    given = parts[1].replace("<", " ").strip() or None
    return surname, given


def parse_mrz(ocr_text: str) -> dict[str, Any] | None:
    """Parst TD1 (Personalausweis) oder TD3 (Reisepass) aus OCR-Output.

    Returns dict mit erkannten Feldern, oder None wenn keine MRZ erkennbar.

    Erkannte Felder (je nach Typ):
      mrz_format, doc_type, doc_country, doc_number, nationality,
      birth_date, sex, expiry, surname, given_names

    KEINE Check-Digit-Verifikation in dieser Funktion — Caller setzt
    mrz_check_ok aus eigener Logik.
    """
    lines = _find_mrz_lines(ocr_text)
    if len(lines) < 2:
        return None

    # TD1: 3 Zeilen à ~30
    if len(lines) >= 3 and all(_TD1_LEN - 2 <= len(ln) <= _TD1_LEN + 2 for ln in lines[:3]):
        return _parse_td1(lines[0], lines[1], lines[2])

    # TD3: 2 Zeilen à ~44
    if len(lines) >= 2 and all(_TD3_LEN - 4 <= len(ln) <= _TD3_LEN + 4 for ln in lines[:2]):
        return _parse_td3(lines[0], lines[1])

    return None


def _parse_td1(l1: str, l2: str, l3: str) -> dict[str, Any]:
    """TD1 / ID-Card. L1: doc-info, L2: birth+gender+expiry+nationality, L3: name."""
    result: dict[str, Any] = {"mrz_format": "TD1", "raw_lines": [l1, l2, l3]}
    try:
        result["doc_type"] = l1[0:2].replace("<", "").strip() or None
        result["doc_country"] = l1[2:5].replace("<", "").strip() or None
        result["doc_number"] = l1[5:14].replace("<", "").strip() or None
        result["birth_date"] = _yymmdd_to_iso(l2[0:6])
        result["sex"] = l2[7] if len(l2) > 7 and l2[7] in "MF" else None
        result["expiry"] = _yymmdd_to_iso(l2[8:14])
        result["nationality"] = l2[15:18].replace("<", "").strip() or None
        surname, given = _split_name(l3)
        result["surname"] = surname
        result["given_names"] = given
    except (IndexError, ValueError) as exc:
        result["parse_error"] = str(exc)
    return result


def _parse_td3(l1: str, l2: str) -> dict[str, Any]:
    """TD3 / Reisepass. L1: name + doc-info, L2: doc-number+nationality+birth+gender+expiry."""
    result: dict[str, Any] = {"mrz_format": "TD3", "raw_lines": [l1, l2]}
    try:
        result["doc_type"] = l1[0:2].replace("<", "").strip() or None
        result["doc_country"] = l1[2:5].replace("<", "").strip() or None
        surname, given = _split_name(l1[5:])
        result["surname"] = surname
        result["given_names"] = given
        result["doc_number"] = l2[0:9].replace("<", "").strip() or None
        result["nationality"] = l2[10:13].replace("<", "").strip() or None
        result["birth_date"] = _yymmdd_to_iso(l2[13:19])
        result["sex"] = l2[20] if len(l2) > 20 and l2[20] in "MF" else None
        result["expiry"] = _yymmdd_to_iso(l2[21:27])
    except (IndexError, ValueError) as exc:
        result["parse_error"] = str(exc)
    return result


# ============================================================ Whitelist-Filter


# MRZ-Felder → Spec-Whitelist-Namen
# (Spec at.yaml verwendet deutsche Namen für DSGVO-Verträglichkeit;
#  Mapping macht's deklarativ.)
_FIELD_ALIASES = {
    "vorname":        ["given_names"],
    "nachname":       ["surname"],
    "geburtsdatum":   ["birth_date"],
    "ausweis_typ":    ["doc_type", "doc_country", "mrz_format"],
    "ablauf":         ["expiry"],
    # ausweisnummer_hash wird IM CALLER aus doc_number gehasht; hier nichts
    # weiterleiten — doc_number darf NICHT in mrz_parsed landen.
}


def filter_mrz_to_whitelist(
    parsed: dict[str, Any] | None,
    allowed_fields: list[str],
) -> dict[str, Any]:
    """Filtert MRZ-Parse-Output auf jurisdictions-Whitelist.

    Alles was nicht in allowed_fields ist, wird verworfen. Spec-Felder werden
    auf interne MRZ-Keys gemappt (siehe _FIELD_ALIASES). 'ausweisnummer_hash'
    wird durchgereicht aber NICHT befüllt — Caller setzt das separat (Hash
    wird in identity_persons.doc_number_hash gespeichert, nicht in der JSONB).

    KRITISCH: doc_number wird NIE durchgereicht, auch nicht wenn
    'ausweisnummer' (ohne _hash) in allowed_fields wäre — wir whitelisten
    nur explizit gemappte Felder.
    """
    if not parsed:
        return {}
    out: dict[str, Any] = {}
    for spec_name in allowed_fields:
        internal_keys = _FIELD_ALIASES.get(spec_name)
        if not internal_keys:
            # ausweisnummer_hash: nicht in MRZ, sondern in Caller-Logik
            continue
        for k in internal_keys:
            if k in parsed and parsed[k] is not None:
                out[k] = parsed[k]
    return out


# ============================================================ Normalize + Hash


def normalize_doc_number(raw: str) -> str:
    """Kanonische Form für Hash-Eingabe (Spec §7.1).

    Schritte (in dieser Reihenfolge):
      1. strip()      — äußerer Whitespace (OCR-Padding)
      2. re.sub(\\s+) — innerer Whitespace (OCR-Artefakte)
      3. upper()      — Case-Folding (KEIN casefold(), Locale-Drift)

    Bewusst NICHT: Sonderzeichen-Filter, führende-Nullen-Strip, Unicode-NFC.
    """
    s = raw.strip()
    s = re.sub(r"\s+", "", s)
    s = s.upper()
    return s


def hash_doc_number(
    normalized: str,
    tenant_salt: str,
    hex_length: int = 24,
) -> str:
    """SHA-256-Hash mit per-Tenant-Salt, getrimmt auf hex_length.

    hex_length default 24 (96-bit), kommt aus jurisdiction.hash_length_hex.
    Cross-Tenant-Trennung: gleicher doc_number in zwei Tenants → andere Salts
    → andere Hashes → kein Cross-Tenant-Identity-Lookup möglich.
    """
    if not normalized:
        raise ValueError("normalized doc_number darf nicht leer sein")
    if not tenant_salt:
        raise ValueError("tenant_salt darf nicht leer sein")
    digest = hashlib.sha256((normalized + tenant_salt).encode("utf-8")).hexdigest()
    return digest[:hex_length]
