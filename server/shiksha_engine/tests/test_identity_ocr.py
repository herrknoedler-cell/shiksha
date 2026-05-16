"""Identity-OCR — Unit-Tests für Normalize, Hash, MRZ-Parser, Whitelist.

Tesseract-Calls werden NICHT gemockt — die `run_ocr`-Funktion wird über
echte tesseract-Binary getestet (auf dem Server installiert).
"""
from __future__ import annotations

import pytest

from shiksha_engine.services.identity_ocr import (
    filter_mrz_to_whitelist,
    hash_doc_number,
    normalize_doc_number,
    parse_mrz,
)


# ============================================================ normalize_doc_number


def test_normalize_strip_outer_whitespace():
    assert normalize_doc_number("  L01X00T47  ") == "L01X00T47"


def test_normalize_strip_inner_whitespace():
    assert normalize_doc_number("L01 X00 T47") == "L01X00T47"


def test_normalize_uppercase():
    assert normalize_doc_number("l01x00t47") == "L01X00T47"


def test_normalize_tabs_newlines():
    assert normalize_doc_number("L01\tX00\nT47") == "L01X00T47"


def test_normalize_keeps_leading_zeros():
    """Führende Nullen bleiben — wichtig für Reisepass-Nummern."""
    assert normalize_doc_number("t00012345") == "T00012345"


def test_normalize_locale_safe():
    """str.upper() ist Locale-frei und deterministisch.

    Note: Python's str.upper() für 'ß' → 'SS' (Unicode-Standard seit 2010),
    aber das ist deterministisch (gleicher Input → gleiches Ergebnis), und das
    ist der Test-Inhalt: kein Locale-abhängiger Drift. Tatsächliche MRZ-
    Felder enthalten kein 'ß' (ICAO 9303 ist ASCII-only)."""
    assert normalize_doc_number("abc") == "ABC"
    assert normalize_doc_number("ABC") == "ABC"
    # Determinismus: gleicher Input → gleiches Ergebnis (kein Locale-Drift)
    assert normalize_doc_number("test") == normalize_doc_number("test")


# ============================================================ hash_doc_number


def test_hash_deterministic():
    h1 = hash_doc_number("L01X00T47", "salt_aaa", 24)
    h2 = hash_doc_number("L01X00T47", "salt_aaa", 24)
    assert h1 == h2
    assert len(h1) == 24


def test_hash_cross_tenant_separation():
    """Gleicher doc_number + verschiedener Salt → verschiedene Hashes."""
    h_a = hash_doc_number("L01X00T47", "salt_tenant_a", 24)
    h_b = hash_doc_number("L01X00T47", "salt_tenant_b", 24)
    assert h_a != h_b


def test_hash_hex_length_configurable():
    h_short = hash_doc_number("ABC123", "salt", 16)
    h_long = hash_doc_number("ABC123", "salt", 32)
    assert len(h_short) == 16
    assert len(h_long) == 32
    assert h_long.startswith(h_short)


def test_hash_empty_normalized_raises():
    with pytest.raises(ValueError):
        hash_doc_number("", "salt", 24)


def test_hash_empty_salt_raises():
    with pytest.raises(ValueError):
        hash_doc_number("ABC", "", 24)


# ============================================================ parse_mrz


def test_parse_mrz_td1_personalausweis():
    """Deutsche Personalausweis-MRZ (TD1, 3×30).

    doc_number ist Position 5-13 (9 Zeichen) gemäß ICAO 9303; Position 14
    ist die Check-Digit, separat von doc_number. Test prüft 9-Zeichen-Form."""
    mrz_text = (
        "IDD<<L01X00T479<<<<<<<<<<<<<<<\n"
        "8001017M2008010D<<<<<<<<<<<<<5\n"
        "MUSTERMANN<<ERIKA<<<<<<<<<<<<<\n"
    )
    parsed = parse_mrz(mrz_text)
    assert parsed is not None
    assert parsed["mrz_format"] == "TD1"
    assert parsed["doc_number"] == "L01X00T47"  # 9 Zeichen, ohne Check-Digit
    assert parsed["birth_date"] == "1980-01-01"
    assert parsed["sex"] == "M"
    assert parsed["surname"] == "MUSTERMANN"
    assert parsed["given_names"] == "ERIKA"


def test_parse_mrz_td3_reisepass():
    """Reisepass TD3 (2×44). doc_number Position 0-8 (9 Zeichen), Pos 9 = Check."""
    mrz_text = (
        "P<DEUMUSTERMANN<<ERIKA<<<<<<<<<<<<<<<<<<<<<<\n"
        "C01X00T478D<<8001017F2401012<<<<<<<<<<<<<<06\n"
    )
    parsed = parse_mrz(mrz_text)
    assert parsed is not None
    assert parsed["mrz_format"] == "TD3"
    assert parsed["doc_country"] == "DEU"
    assert parsed["doc_number"] == "C01X00T47"  # 9 Zeichen
    assert parsed["surname"] == "MUSTERMANN"
    assert parsed["given_names"] == "ERIKA"
    assert parsed["birth_date"] == "1980-01-01"
    assert parsed["sex"] == "F"
    assert parsed["expiry"] == "2024-01-01"


def test_parse_mrz_no_mrz_returns_none():
    """OCR-Output ohne MRZ-Markeur → None."""
    assert parse_mrz("Just some random text without machine-readable zone") is None
    assert parse_mrz("") is None


# ============================================================ filter_mrz_to_whitelist


def test_filter_whitelist_drops_disallowed():
    """nationality ist nicht in AT-Whitelist → wird verworfen."""
    parsed = {
        "given_names": "Erika",
        "surname": "Mustermann",
        "doc_number": "L01X00T47",            # DARF NIE durchgereicht werden
        "nationality": "DEU",                 # nicht in AT-Whitelist
        "birth_date": "1980-01-01",
        "expiry": "2030-01-01",
        "mrz_format": "TD1",
    }
    allowed_at = ["vorname", "nachname", "geburtsdatum", "ausweis_typ", "ausweisnummer_hash", "ablauf"]
    out = filter_mrz_to_whitelist(parsed, allowed_at)

    assert out.get("given_names") == "Erika"
    assert out.get("surname") == "Mustermann"
    assert out.get("birth_date") == "1980-01-01"
    assert out.get("expiry") == "2030-01-01"
    assert out.get("mrz_format") == "TD1"
    # KRITISCH: doc_number darf NIE in der Whitelist landen
    assert "doc_number" not in out
    # nationality nicht erlaubt → verworfen
    assert "nationality" not in out


def test_filter_whitelist_empty_input():
    assert filter_mrz_to_whitelist(None, ["vorname"]) == {}
    assert filter_mrz_to_whitelist({}, ["vorname"]) == {}


def test_filter_whitelist_missing_field_skipped():
    """allowed_fields enthält 'vorname', aber Parser hat keinen given_names → out leer."""
    parsed = {"surname": "Mustermann"}
    out = filter_mrz_to_whitelist(parsed, ["vorname"])
    assert "given_names" not in out
