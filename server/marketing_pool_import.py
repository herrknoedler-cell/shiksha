#!/usr/bin/env python3
"""
SHIKSHA · Pool-Importer
Liest /opt/shiksha/marketing_assets/pool/<edition>/<season>/*.jpg und
schreibt Datensätze in marketing_assets als Pool-Bilder (site_id = NULL).
Idempotent — gleiche Datei wird nicht doppelt importiert (wir matchen
auf file_path).

Aufruf:
  /opt/shiksha/venv/bin/python /opt/shiksha/marketing_pool_import.py
"""

import os
import sys
import pathlib
import sqlalchemy as sa

DB_URL = os.environ.get("DATABASE_URL") or "postgresql://shiksha:shiksha@127.0.0.1/shiksha"
engine = sa.create_engine(DB_URL)

POOL_ROOT = pathlib.Path("/opt/shiksha/marketing_assets/pool")

count_imported = 0
count_skipped = 0

if not POOL_ROOT.exists():
    print(f"Pool-Ordner {POOL_ROOT} existiert nicht.")
    sys.exit(0)

with engine.begin() as conn:
    for edition_dir in POOL_ROOT.iterdir():
        if not edition_dir.is_dir(): continue
        for season_dir in edition_dir.iterdir():
            if not season_dir.is_dir(): continue
            for img_file in season_dir.glob("*.jpg"):
                fp = str(img_file)
                # Schon importiert?
                exists = conn.execute(sa.text(
                    "SELECT id FROM marketing_assets WHERE file_path = :fp"),
                    {"fp": fp}).first()
                if exists:
                    count_skipped += 1
                    continue
                conn.execute(sa.text("""
                    INSERT INTO marketing_assets
                      (site_id, pool_edition, pool_season, file_path, mime_type, alt_text, source)
                    VALUES (NULL, :ed, :se, :fp, 'image/jpeg', :alt, 'firefly')
                """), {
                    "ed": edition_dir.name,
                    "se": season_dir.name,
                    "fp": fp,
                    "alt": f"{edition_dir.name} {season_dir.name} — SHIKSHA-Pool",
                })
                count_imported += 1

print(f"✓ {count_imported} neue Pool-Bilder importiert")
print(f"↪ {count_skipped} schon vorhanden, übersprungen")
