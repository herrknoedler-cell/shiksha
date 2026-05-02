# database_additions.py
# document.module V1 — additions to database.py
#
# HOW TO INTEGRATE:
# 1. Copy the three Table definitions below into database.py
#    alongside your existing `entities`, `memory_records`, `event_records` tables.
# 2. Copy the init_document_tables() call into your existing init_db() function.
# 3. Copy the four helper functions at the bottom into database.py.
#
# The existing database.py structure is unchanged. These are additive only.

from sqlalchemy import (
    Table, Column, String, Float, Text, DateTime,
    MetaData, create_engine
)
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paste these Table objects into database.py alongside existing tables
# ---------------------------------------------------------------------------

# Assumes `metadata` and `engine` already exist in database.py

def define_document_tables(metadata: MetaData):
    """
    Call this after your existing table definitions.
    Returns the three new table objects.
    """

    documents = Table(
        "documents",
        metadata,
        Column("id",            String,   primary_key=True),
        Column("edition",       String,   nullable=False),
        Column("document_type", String,   nullable=False),   # invoice|offer|contract|note|unknown
        Column("source_type",   String,   nullable=False),   # text|pdf|image
        Column("raw_text",      Text,     nullable=False),
        Column("status",        String,   nullable=False, default="analyzed"),  # raw|analyzed|linked
        Column("created_at",    DateTime, nullable=False),
        extend_existing=True,
    )

    document_field_candidates = Table(
        "document_field_candidates",
        metadata,
        Column("id",          String,  primary_key=True),
        Column("document_id", String,  nullable=False),   # FK → documents.id
        Column("field_key",   String,  nullable=False),
        Column("field_value", String,  nullable=False),
        Column("confidence",  Float,   nullable=False),
        Column("created_at",  DateTime, nullable=False),
        extend_existing=True,
    )

    document_links = Table(
        "document_links",
        metadata,
        Column("id",            String,  primary_key=True),
        Column("document_id",   String,  nullable=False),   # FK → documents.id
        Column("entity_type",   String,  nullable=False),   # customer
        Column("entity_id",     String,  nullable=False),
        Column("link_type",     String,  nullable=False, default="belongs_to"),
        Column("confidence",    Float,   nullable=False),
        Column("review_status", String,  nullable=False),   # proposed|confirmed|corrected
        Column("created_at",    DateTime, nullable=False),
        Column("confirmed_at",  DateTime, nullable=True),
        extend_existing=True,
    )

    return documents, document_field_candidates, document_links


# ---------------------------------------------------------------------------
# Add this call inside your existing init_db() function in database.py
# ---------------------------------------------------------------------------

def init_document_tables(engine, metadata):
    """
    Creates document tables if they don't exist.
    Safe to call on every startup (CREATE TABLE IF NOT EXISTS behavior via checkfirst=True).
    """
    metadata.create_all(engine, checkfirst=True)


# ---------------------------------------------------------------------------
# DB helper functions — paste into database.py
# ---------------------------------------------------------------------------

import uuid

def save_document(conn, tables, document_id: str, edition: str,
                  document_type: str, source_type: str,
                  raw_text: str, status: str = "analyzed"):
    conn.execute(tables["documents"].insert().values(
        id=document_id,
        edition=edition,
        document_type=document_type,
        source_type=source_type,
        raw_text=raw_text,
        status=status,
        created_at=datetime.now(timezone.utc),
    ))


def save_field_candidates(conn, tables, document_id: str, candidates: list):
    for c in candidates:
        conn.execute(tables["document_field_candidates"].insert().values(
            id=str(uuid.uuid4()),
            document_id=document_id,
            field_key=c.field_key,
            field_value=c.field_value,
            confidence=c.confidence,
            created_at=datetime.now(timezone.utc),
        ))


def save_document_link(conn, tables, document_id: str, entity_type: str,
                       entity_id: str, link_type: str, confidence: float,
                       review_status: str) -> str:
    link_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    conn.execute(tables["document_links"].insert().values(
        id=link_id,
        document_id=document_id,
        entity_type=entity_type,
        entity_id=entity_id,
        link_type=link_type,
        confidence=confidence,
        review_status=review_status,
        created_at=now,
        confirmed_at=now,
    ))
    return link_id


def update_document_status(conn, tables, document_id: str, new_status: str):
    conn.execute(
        tables["documents"].update()
        .where(tables["documents"].c.id == document_id)
        .values(status=new_status)
    )
