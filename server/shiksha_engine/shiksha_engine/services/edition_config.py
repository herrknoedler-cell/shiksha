"""EditionConfig-Loader — liest editions/*.yaml und cached sie.

Pro Edition (kita, camping, schule, surf, yoga, club) eine yaml mit:
  - vocabulary (operator_role, org_word, member_word, pain_words, …)
  - tools (Liste verfügbarer Tool-Namen)
  - dashboard_cards (Standard-Card-Set)
  - site_template (Name des Generation-Templates)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from ..settings import get_settings


@lru_cache(maxsize=16)
def get_edition_config(edition: str) -> dict | None:
    """Liest editions/<edition>.yaml. Cached. None wenn nicht vorhanden."""
    settings = get_settings()
    path = Path(settings.editions_dir) / f"{edition}.yaml"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def list_editions() -> list[str]:
    """Welche Editions sind via yaml definiert?"""
    settings = get_settings()
    path = Path(settings.editions_dir)
    if not path.exists():
        return []
    return sorted([p.stem for p in path.glob("*.yaml")])


def reload_cache() -> None:
    """Cache leeren (für Entwicklung wenn yamls editiert wurden)."""
    get_edition_config.cache_clear()
