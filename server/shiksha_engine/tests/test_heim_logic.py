"""Heim-Logik-Tests — Provider, Visibility-Rules, Loader.

Direkt-Tests gegen die Service-Funktionen, ohne HTTP-Layer.
API-Tests siehe test_heim_endpoints.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from shiksha_engine.models import (
    MemoryEntry,
    Session as ShikshaSession,
    TenantHeimConfig,
)
from shiksha_engine.services.heim_loader import (
    _current_slot,
    _greeting_for,
    load_heim,
)
from shiksha_engine.services.heim_providers import (
    call_provider,
    evaluate_visibility,
    list_providers,
    register_provider,
    render_subtitle,
)


# ===================================================================
# Tageszeit-Slots + Greeting
# ===================================================================

def test_current_slot_boundaries():
    assert _current_slot(5)  == "morning"
    assert _current_slot(11) == "morning"
    assert _current_slot(12) == "afternoon"
    assert _current_slot(16) == "afternoon"
    assert _current_slot(17) == "evening"
    assert _current_slot(21) == "evening"
    assert _current_slot(22) == "night"
    assert _current_slot(4)  == "night"


def test_greeting_includes_name():
    g = _greeting_for("morning", "Mira")
    assert "Mira" in g
    assert "Morgen" in g


def test_greeting_handles_empty_name():
    g = _greeting_for("evening", "")
    assert "Abend" in g


def test_greeting_all_slots_distinct():
    name = "Mira"
    slots = ["morning", "afternoon", "evening", "night"]
    greetings = [_greeting_for(s, name) for s in slots]
    assert len(set(greetings)) == 4


# ===================================================================
# Visibility-Rule-Auswerter
# ===================================================================

def test_visibility_rule_empty_returns_true():
    assert evaluate_visibility(None, {}) is True
    assert evaluate_visibility("", {}) is True


def test_visibility_rule_count_greater_than():
    assert evaluate_visibility("count > 0", {"count": 3}) is True
    assert evaluate_visibility("count > 0", {"count": 0}) is False
    assert evaluate_visibility("count > 5", {"count": 5}) is False


def test_visibility_rule_count_greater_equal():
    assert evaluate_visibility("count >= 2", {"count": 2}) is True
    assert evaluate_visibility("count >= 2", {"count": 1}) is False


def test_visibility_rule_visible_false_overrides():
    """Wenn Provider sagt visible=False, gewinnt das immer."""
    assert evaluate_visibility(None, {"visible": False}) is False
    assert evaluate_visibility("count > 0", {"count": 5, "visible": False}) is False


def test_visibility_rule_not_field():
    assert evaluate_visibility("not empty", {"empty": False}) is True
    assert evaluate_visibility("not empty", {"empty": True}) is False


def test_visibility_rule_missing_field_returns_false():
    assert evaluate_visibility("count > 0", {}) is False


def test_visibility_rule_garbage_returns_false():
    """Bei unsinniger Rule-Syntax: konservativ False."""
    assert evaluate_visibility("garbage @@@ syntax", {"count": 5}) is False


# ===================================================================
# Subtitle-Template-Renderer
# ===================================================================

def test_render_subtitle_substitutes_fields():
    out = render_subtitle("{count} Notizen", {"count": 3})
    assert out == "3 Notizen"


def test_render_subtitle_handles_missing_field():
    out = render_subtitle("{count} of {total}", {"count": 5})
    # Fehlende Felder → Original-Template
    assert out == "{count} of {total}"


def test_render_subtitle_none_template():
    assert render_subtitle(None, {"count": 1}) is None


def test_render_subtitle_empty_template():
    assert render_subtitle("", {}) == ""


# ===================================================================
# Provider-Registry
# ===================================================================

def test_provider_registry_has_core_providers():
    names = list_providers()
    assert "memory_proposed_count" in names
    assert "verlauf_count" in names
    assert "kita_anwesenheit_stub" in names


def test_unknown_provider_returns_invisible():
    result = call_provider("doesnt_exist", None, None)
    assert result == {"visible": False}


def test_provider_with_exception_returns_invisible(db, mira_leitung):
    """Provider, der eine Exception wirft, lässt die Karte verschwinden."""
    @register_provider("test_raises_provider")
    def _bad(operator, db_):
        raise RuntimeError("kaputt")

    result = call_provider("test_raises_provider", mira_leitung, db)
    assert result == {"visible": False}


def test_memory_proposed_count_provider(db, mira_leitung):
    """Provider zählt nur proposed Memories, keine active."""
    # Eine active Memory — sollte nicht zählen
    db.add(MemoryEntry(
        operator_id=mira_leitung.id, edition=mira_leitung.edition,
        text="active 1", status="active",
    ))
    # Zwei proposed
    db.add(MemoryEntry(
        operator_id=mira_leitung.id, edition=mira_leitung.edition,
        text="proposed 1", status="proposed",
    ))
    db.add(MemoryEntry(
        operator_id=mira_leitung.id, edition=mira_leitung.edition,
        text="proposed 2", status="proposed",
    ))
    db.commit()

    from shiksha_engine.services.heim_providers import _memory_proposed
    result = _memory_proposed(mira_leitung, db)
    assert result["count"] == 2
    assert result["visible"] is True


def test_memory_proposed_count_zero_means_invisible(db, mira_leitung):
    from shiksha_engine.services.heim_providers import _memory_proposed
    result = _memory_proposed(mira_leitung, db)
    assert result["count"] == 0
    assert result["visible"] is False


def test_verlauf_count_only_closed_sessions(db, mira_leitung):
    """Provider zählt nur abgeschlossene Sessions."""
    db.add(ShikshaSession(
        id="ses_open",
        operator_id=mira_leitung.id, org_id=mira_leitung.org_id,
        edition="kita", persona="tagesausklang",
    ))
    db.add(ShikshaSession(
        id="ses_closed",
        operator_id=mira_leitung.id, org_id=mira_leitung.org_id,
        edition="kita", persona="tagesausklang",
        closed_at=datetime.now(timezone.utc),
    ))
    db.commit()

    from shiksha_engine.services.heim_providers import _verlauf_count
    result = _verlauf_count(mira_leitung, db)
    assert result["count"] == 1


def test_identity_summary_counts_pending_and_expiring(db, mira_leitung):
    """Provider zählt pending IdentityPersons + verified mit doc_expiry < 30d."""
    from datetime import date, timedelta
    from shiksha_engine.models import IdentityPerson
    from shiksha_engine.services.heim_providers import _identity_summary

    now = datetime.now(timezone.utc)
    today = date.today()

    # 3× pending
    for i in range(3):
        db.add(IdentityPerson(
            tenant_org_id=mira_leitung.org_id,
            full_name=f"Pending {i}",
            consent_given=True,
            verification_status="pending",
            created_at=now, updated_at=now,
        ))
    # 1× verified mit doc_expiry in 14d (zählt als expiring)
    db.add(IdentityPerson(
        tenant_org_id=mira_leitung.org_id,
        full_name="Expiring Bald",
        consent_given=True,
        verification_status="verified",
        verified_at=now,
        doc_expiry=today + timedelta(days=14),
        created_at=now, updated_at=now,
    ))
    # 1× verified mit doc_expiry in 90d (NICHT expiring)
    db.add(IdentityPerson(
        tenant_org_id=mira_leitung.org_id,
        full_name="Expiring Spät",
        consent_given=True,
        verification_status="verified",
        verified_at=now,
        doc_expiry=today + timedelta(days=90),
        created_at=now, updated_at=now,
    ))
    db.commit()

    result = _identity_summary(mira_leitung, db)
    assert result["pending_count"] == 3
    assert result["expiring_soon_count"] == 1
    assert "3 zu prüfen" in result["subtitle"]
    assert "1 läuft ab" in result["subtitle"]
    assert result["visible"] is True


def test_identity_summary_empty_state(db, mira_leitung):
    """Bei nichts zu tun: subtitle = 'Alles geprüft'."""
    from shiksha_engine.services.heim_providers import _identity_summary
    result = _identity_summary(mira_leitung, db)
    assert result["pending_count"] == 0
    assert result["expiring_soon_count"] == 0
    assert result["subtitle"] == "Alles geprüft"


# ===================================================================
# load_heim — Integrations-Test mit echten Edition-YAMLs
# ===================================================================

def test_load_heim_for_leitung_returns_cards(db, mira_leitung):
    """Leitung sieht ihre Karten — mindestens Tagesausklang und Einstellungen."""
    result = load_heim(mira_leitung, db)
    assert result.role == "leitung"
    assert result.tenant == "krummelus_v2"
    assert len(result.cards) >= 2

    card_ids = {c.id for c in result.cards}
    # Core-Cards aus core.yaml
    assert "tagesausklang" in card_ids
    assert "einstellungen" in card_ids


def test_load_heim_for_padagoge_includes_abholer(db, pedagogin):
    """Pädagogin sieht 'Abholer prüfen' (laut KITA-YAML)."""
    result = load_heim(pedagogin, db)
    card_ids = {c.id for c in result.cards}
    assert "abholer_pruefen" in card_ids


def test_load_heim_passes_size_and_holi_border(db, pedagogin):
    """T-013: size + holi_border aus YAML kommen in der HeimCard an
    (für CSS-Modifier im Frontend). abholer_pruefen hat size='2x2'
    und holi_border='tuerkis' aus 5.5.6.6.a-Pre-Sale."""
    result = load_heim(pedagogin, db)
    abholer = next((c for c in result.cards if c.id == "abholer_pruefen"), None)
    assert abholer is not None
    assert abholer.size == "2x2"
    assert abholer.holi_border == "tuerkis"


def test_load_heim_for_padagoge_excludes_leitung_only(db, pedagogin):
    """personal_heute ist role_scope=['leitung'] — Pädagogin sieht das nicht."""
    result = load_heim(pedagogin, db)
    card_ids = {c.id for c in result.cards}
    assert "personal_heute" not in card_ids


def test_load_heim_for_eltern_shows_stub(db, vater):
    """Eltern in Phase 1: Stub-Karte 'Demnächst hier'."""
    result = load_heim(vater, db)
    card_ids = {c.id for c in result.cards}
    assert "stub_klienten_demnaechst" in card_ids


def test_load_heim_for_eltern_excludes_staff_cards(db, vater):
    """Eltern sehen keine Staff-Karten wie Tagesausklang oder Anwesenheit."""
    result = load_heim(vater, db)
    card_ids = {c.id for c in result.cards}
    assert "tagesausklang" not in card_ids
    assert "anwesenheit_today" not in card_ids
    assert "personal_heute" not in card_ids


def test_load_heim_greeting_morning(db, mira_leitung):
    """Greeting passt zur Tageszeit."""
    with patch("shiksha_engine.services.heim_loader.datetime") as mock_dt:
        mock_dt.now.return_value.hour = 8
        result = load_heim(mira_leitung, db)
    assert "Morgen" in result.greeting
    assert "Mira" in result.greeting


def test_load_heim_greeting_evening(db, mira_leitung):
    with patch("shiksha_engine.services.heim_loader.datetime") as mock_dt:
        mock_dt.now.return_value.hour = 19
        result = load_heim(mira_leitung, db)
    assert "Abend" in result.greeting


def test_load_heim_sorting_morning_vs_evening(db, mira_leitung):
    """Anwesenheit morgens prio 1, abends prio 7 — Reihenfolge wechselt."""
    with patch("shiksha_engine.services.heim_loader.datetime") as mock_dt:
        mock_dt.now.return_value.hour = 8
        morning = load_heim(mira_leitung, db)
    with patch("shiksha_engine.services.heim_loader.datetime") as mock_dt:
        mock_dt.now.return_value.hour = 20
        evening = load_heim(mira_leitung, db)

    morning_ids = [c.id for c in morning.cards]
    evening_ids = [c.id for c in evening.cards]

    # Anwesenheit ist morgens weiter vorn als Tagesausklang
    if "anwesenheit_today" in morning_ids and "tagesausklang" in morning_ids:
        assert morning_ids.index("anwesenheit_today") < morning_ids.index("tagesausklang")

    # Abends ist Tagesausklang weiter vorn als Anwesenheit
    if "anwesenheit_today" in evening_ids and "tagesausklang" in evening_ids:
        assert evening_ids.index("tagesausklang") < evening_ids.index("anwesenheit_today")


def test_load_heim_memory_proposed_invisible_when_empty(db, mira_leitung):
    """Memory-Vorschläge-Karte erscheint nur wenn welche da sind."""
    result = load_heim(mira_leitung, db)
    card_ids = {c.id for c in result.cards}
    assert "memory_proposed" not in card_ids


def test_load_heim_memory_proposed_visible_when_present(db, mira_leitung):
    db.add(MemoryEntry(
        operator_id=mira_leitung.id, edition=mira_leitung.edition,
        text="ein Vorschlag", status="proposed",
    ))
    db.commit()

    result = load_heim(mira_leitung, db)
    card_ids = {c.id for c in result.cards}
    assert "memory_proposed" in card_ids


def test_load_heim_respects_disabled_override(db, mira_leitung):
    """Wenn Leitung eine Karte deaktiviert, fällt sie aus dem Heim."""
    db.add(TenantHeimConfig(
        org_id=mira_leitung.org_id,
        role=mira_leitung.role,
        card_id="tagesausklang",
        enabled=False,
    ))
    db.commit()

    result = load_heim(mira_leitung, db)
    card_ids = {c.id for c in result.cards}
    assert "tagesausklang" not in card_ids


def test_load_heim_respects_custom_title_override(db, mira_leitung):
    db.add(TenantHeimConfig(
        org_id=mira_leitung.org_id,
        role=mira_leitung.role,
        card_id="tagesausklang",
        enabled=True,
        custom_title="Mein Tagesabschluss",
    ))
    db.commit()

    result = load_heim(mira_leitung, db)
    card = next((c for c in result.cards if c.id == "tagesausklang"), None)
    assert card is not None
    assert card.title == "Mein Tagesabschluss"


def test_load_heim_no_duplicates_when_card_in_core_and_edition(db, mira_leitung):
    """Wenn dieselbe card_id in core.yaml UND kita.yaml stünde — keine doppelten."""
    result = load_heim(mira_leitung, db)
    ids = [c.id for c in result.cards]
    assert len(ids) == len(set(ids))
