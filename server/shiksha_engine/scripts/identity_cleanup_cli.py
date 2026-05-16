"""CLI für Identity-Cleanup-Job (T-011, manuelles Pre-Cron-Tool).

Beispiele:
  python -m scripts.identity_cleanup_cli --tier 1 --dry-run
  python -m scripts.identity_cleanup_cli --tier 1 --execute
  python -m scripts.identity_cleanup_cli --all --dry-run
  python -m scripts.identity_cleanup_cli --all --execute --tenant krummelus
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from shiksha_engine.db import SessionLocal
from shiksha_engine.services.identity_cleanup import (
    cleanup_tier_1_files,
    cleanup_tier_2_structured,
    cleanup_tier_3_audit_log,
    run_all_tiers,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Identity-Cleanup-CLI (T-011)")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--tier", type=int, choices=[1, 2, 3], help="Nur diesen Tier laufen lassen")
    grp.add_argument("--all", action="store_true", help="Alle drei Tiers nacheinander")
    parser.add_argument("--tenant", default=None, help="Tenant-Org-ID (Default: alle)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Zeige nur was gelöscht würde")
    mode.add_argument("--execute", action="store_true", help="Echte Löschung durchführen")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    dry_run = args.dry_run

    with SessionLocal() as db:
        if args.all:
            result = run_all_tiers(db, tenant_org_id=args.tenant, dry_run=dry_run)
        elif args.tier == 1:
            result = {"tier_1": cleanup_tier_1_files(db, tenant_org_id=args.tenant, dry_run=dry_run)}
        elif args.tier == 2:
            result = {"tier_2": cleanup_tier_2_structured(db, tenant_org_id=args.tenant, dry_run=dry_run)}
        elif args.tier == 3:
            result = {"tier_3": cleanup_tier_3_audit_log(db, tenant_org_id=args.tenant, dry_run=dry_run)}

    mode_label = "DRY-RUN" if dry_run else "EXECUTED"
    print(f"[{mode_label}] result:")
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
