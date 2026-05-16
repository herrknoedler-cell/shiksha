"""Jurisdiction-Loader für editions/jurisdictions/<code>.yaml.

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §3.6.

Resolution-Pattern:
  load_jurisdiction_config("AT-8")
    1. lädt editions/jurisdictions/at.yaml (Country-Default)
    2. wenn editions/jurisdictions/at-8.yaml existiert: deep-merge drüber
    3. returned das merged dict

LRU-Cache hält geladene Configs im Speicher; bei Code-Deploy startet
der Process neu und der Cache leert sich. Bei Live-YAML-Editing (selten)
muss clear_jurisdiction_cache() aufgerufen werden.

Aufruf-Site (typisch aus Provider oder Service):
  policy = operator.organization.jurisdiction_yaml()["identity"]
  retention = policy["retention"]["scan_files_days"]
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


# editions/jurisdictions/ liegt zwei Ebenen über services/ (Repo-Root von
# /server/shiksha_engine ist gleichzeitig Engine-Root mit editions/-Subdir).
# __file__ = .../shiksha_engine/services/jurisdiction.py
# parents[0] = .../shiksha_engine/services
# parents[1] = .../shiksha_engine
# parents[2] = .../  (Engine-Root mit editions/ und alembic/)
JURISDICTIONS_DIR: Path = (
    Path(__file__).resolve().parents[2] / "editions" / "jurisdictions"
)


@lru_cache(maxsize=128)
def load_jurisdiction_config(jurisdiction_code: str) -> dict[str, Any]:
    """Lädt Deep-Merge aus country-default + optional region-override.

    Args:
        jurisdiction_code: ISO 3166-2 Format, case-insensitiv im Lookup
                          ('AT-8' und 'at-8' liefern dasselbe).

    Returns:
        Merged config dict mit `identity` als Hauptschlüssel.

    Raises:
        FileNotFoundError: wenn weder country-default existiert.
        ValueError: bei unparsbarem Code.
    """
    code = jurisdiction_code.strip().lower()
    if not code:
        raise ValueError("jurisdiction_code darf nicht leer sein")

    parts = code.split("-")
    country = parts[0]
    region = code if len(parts) > 1 else None

    country_path = JURISDICTIONS_DIR / f"{country}.yaml"
    if not country_path.exists():
        raise FileNotFoundError(
            f"Jurisdiction country-default fehlt: {country_path} "
            f"(jurisdiction_code={jurisdiction_code!r})"
        )

    config: dict[str, Any] = _load_yaml(country_path)

    if region:
        region_path = JURISDICTIONS_DIR / f"{region}.yaml"
        if region_path.exists():
            override = _load_yaml(region_path)
            config = _deep_merge(config, override)

    return config


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursive merge — override wins for scalars and lists, dicts recurse."""
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def clear_jurisdiction_cache() -> None:
    """Test-Helper — bei Konfig-Änderung zur Laufzeit den LRU-Cache löschen."""
    load_jurisdiction_config.cache_clear()
