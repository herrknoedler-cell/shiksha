"""Seed: Mira (Krummelus-KITA) + Thomas (Developer) als Initial-Operatoren.

Aufruf: python -m scripts.seed_operators
"""

from __future__ import annotations

from sqlalchemy import select

from shiksha_engine.db import db_session
from shiksha_engine.models import Operator, Organization


SEED_ORGS = [
    dict(
        id="krummelus",
        edition="kita",
        name="Krummelus",
        legal_name="Krummelus Familien-KITA",
        region="Vorarlberg, AT",
        metadata={"city": "Dornbirn"},
    ),
]


SEED_OPERATORS = [
    dict(
        id="krummelus_mira",
        org_id="krummelus",
        edition="kita",
        display_name="Mira",
        role="operator",
        email="mira@krummelus.example",
        metadata={"season_preference": "warm-room", "reminder_time": "17:30"},
    ),
    dict(
        id="thomas",
        org_id=None,
        edition="kita",       # Dev-Account braucht eine Default-Edition für edition-aware Tests
        kind="system",        # Developer = kind=system → Cross-Tenant-Access via _scope_query
        display_name="Thomas",
        role="developer",
        email="thomas@shiksha.world",
        metadata={"season_preference": "morning-harbor"},
    ),
]


def seed() -> None:
    with db_session() as db:
        for org_data in SEED_ORGS:
            existing = db.get(Organization, org_data["id"])
            if existing:
                print(f"  · org {org_data['id']} — exists")
                continue
            org = Organization(metadata_=org_data.pop("metadata"), **org_data)
            db.add(org)
            print(f"  ✓ org {org.id} — seeded")

        for op_data in SEED_OPERATORS:
            existing = db.get(Operator, op_data["id"])
            if existing:
                print(f"  · operator {op_data['id']} ({op_data['role']}) — exists")
                continue
            op = Operator(metadata_=op_data.pop("metadata"), **op_data)
            db.add(op)
            print(f"  ✓ operator {op.id} ({op.role}, {op.edition}) — seeded")

        db.commit()


if __name__ == "__main__":
    print("Seeding operators + organizations …")
    seed()
    print("Done.")
