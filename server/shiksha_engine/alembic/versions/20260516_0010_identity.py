"""Migration 0010 — Identity-Modul (5.5.6.1).

Erweitert organizations um zwei Spalten (jurisdiction + identity_salt) und
legt vier Identity-Tabellen an:
  - identity_persons          Stammdaten + Verifikations-Status
  - identity_documents        Datei-Refs + OCR/MRZ-Output (whitelist-gefiltert)
  - identity_authorizations   Wer darf was (target_type/id, valid_from/to)
  - identity_audit_log        DSGVO-Pflicht, jeder Zugriff (Retention 7 Jahre)

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §3.

Wichtig:
- jurisdiction: ISO 3166-2 (z.B. "AT-8" für Vorarlberg). Backfill auf
  "AT-8" für alle bestehenden Tenants (heute nur Krummelus). Neue
  Tenants müssen jurisdiction explicit setzen — Model-Default ist "AT-8".
- identity_salt: per-Tenant-Salt für doc_number_hash. In dieser Migration
  via secrets.token_hex(32) für bestehende Rows generiert; für neue Rows
  liefert das ORM-Model den Default. Kein server_default weil pgcrypto
  nicht installiert ist.
- doc_number_hash in identity_persons: NUR der Hash, NIE die raw doc_number.
  Hash = sha256(doc_number_normalized + tenant_salt)[:24]. Service-Layer
  enforced das.
- mrz_parsed in identity_documents: JSONB, vom Service-Layer whitelist-
  gefiltert auf jurisdiction.mrz_fields_to_store. Raw-Output landet NIE
  in DB.

Revises: 0009_attendance
Create Date: 2026-05-16
"""
import secrets

from alembic import op
import sqlalchemy as sa


revision = "0010_identity"
down_revision = "0009_attendance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # ==================================================================
    # PHASE A — organizations.jurisdiction + organizations.identity_salt
    # ==================================================================

    op.add_column(
        "organizations",
        sa.Column("jurisdiction", sa.String(5), nullable=True),
        schema="shiksha_core",
    )
    op.add_column(
        "organizations",
        sa.Column("identity_salt", sa.String(64), nullable=True),
        schema="shiksha_core",
    )

    # Backfill: alle bestehenden Tenants → 'AT-8' (heute nur Krummelus).
    # Wenn ein Tenant außerhalb von AT existiert: vor Migration manuell
    # jurisdiction setzen via SQL, dann diese Migration laufen lassen.
    bind.execute(sa.text(
        "UPDATE shiksha_core.organizations "
        "SET jurisdiction = 'AT-8' WHERE jurisdiction IS NULL"
    ))

    # identity_salt: pro Row random generieren
    rows = bind.execute(sa.text(
        "SELECT id FROM shiksha_core.organizations WHERE identity_salt IS NULL"
    )).fetchall()
    for row in rows:
        bind.execute(
            sa.text("UPDATE shiksha_core.organizations "
                    "SET identity_salt = :salt WHERE id = :id"),
            {"salt": secrets.token_hex(32), "id": row.id},
        )

    # NOT NULL aktivieren
    op.alter_column(
        "organizations", "jurisdiction",
        existing_type=sa.String(5),
        nullable=False,
        schema="shiksha_core",
    )
    op.alter_column(
        "organizations", "identity_salt",
        existing_type=sa.String(64),
        nullable=False,
        schema="shiksha_core",
    )

    # CHECK-Constraint: ISO 3166-2 Format (Country oder Country-Region)
    op.create_check_constraint(
        "ck_organizations_jurisdiction_format",
        "organizations",
        "jurisdiction ~ '^[A-Z]{2}(-[A-Z0-9]{1,3})?$'",
        schema="shiksha_core",
    )

    # ==================================================================
    # PHASE B.1 — identity_persons
    # ==================================================================

    op.create_table(
        "identity_persons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_org_id",
            sa.Text(),
            sa.ForeignKey("shiksha_core.organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),

        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),

        # Ausweis-Daten (gefiltert / gehashed)
        sa.Column("doc_kind", sa.String(20), nullable=True),
        sa.Column("doc_number_hash", sa.String(24), nullable=True),
        sa.Column("doc_expiry", sa.Date(), nullable=True),

        # Consent
        sa.Column("consent_given", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consent_text", sa.Text(), nullable=True),
        sa.Column("consent_given_at", sa.TIMESTAMP(timezone=True), nullable=True),

        # Verifikation
        sa.Column(
            "verification_status", sa.String(20),
            nullable=False, server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "verified_by_operator_id",
            sa.String(64),
            sa.ForeignKey("shiksha_core.operators.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True), nullable=True),

        # Verknüpfung zu persons (optional, kann NULL bleiben)
        sa.Column(
            "linked_person_id",
            sa.Integer(),
            sa.ForeignKey("shiksha_core.persons.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # Lifecycle
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("structured_delete_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),

        sa.CheckConstraint(
            "verification_status IN ('pending', 'verified', 'rejected')",
            name="ck_identity_persons_status",
        ),
        sa.CheckConstraint(
            "doc_kind IS NULL OR doc_kind IN ('personalausweis', 'reisepass', 'other')",
            name="ck_identity_persons_doc_kind",
        ),
        schema="shiksha_core",
    )

    op.create_index(
        "ix_identity_persons_tenant",
        "identity_persons", ["tenant_org_id"],
        schema="shiksha_core",
    )
    op.create_index(
        "ix_identity_persons_pending",
        "identity_persons", ["verification_status"],
        postgresql_where=sa.text("verification_status = 'pending'"),
        schema="shiksha_core",
    )
    op.create_index(
        "ix_identity_persons_linked",
        "identity_persons", ["linked_person_id"],
        postgresql_where=sa.text("linked_person_id IS NOT NULL"),
        schema="shiksha_core",
    )

    # ==================================================================
    # PHASE B.2 — identity_documents
    # ==================================================================

    op.create_table(
        "identity_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "identity_person_id",
            sa.Integer(),
            sa.ForeignKey("shiksha_core.identity_persons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("doc_kind", sa.String(20), nullable=False),

        # File-Ref (NULL nach Tier-1-Auto-Delete, ~30 Tage)
        sa.Column("file_ref", sa.Text(), nullable=True),
        sa.Column("file_deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("mime_type", sa.String(50), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),

        # Integritäts-Nachweis (bleibt auch nach File-Delete)
        sa.Column("original_hash", sa.String(64), nullable=False),

        # OCR + MRZ
        sa.Column("ocr_output", sa.Text(), nullable=True),
        sa.Column("ocr_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "mrz_parsed",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column("mrz_check_ok", sa.Boolean(), nullable=True),

        # Audit
        sa.Column(
            "uploaded_by_operator_id",
            sa.String(64),
            sa.ForeignKey("shiksha_core.operators.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploaded_at", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),

        sa.CheckConstraint(
            "doc_kind IN ('id_front', 'id_back', 'passport', 'other')",
            name="ck_identity_documents_kind",
        ),
        schema="shiksha_core",
    )

    op.create_index(
        "ix_identity_documents_person",
        "identity_documents", ["identity_person_id"],
        schema="shiksha_core",
    )
    op.create_index(
        "ix_identity_documents_file_expiry",
        "identity_documents", ["uploaded_at"],
        postgresql_where=sa.text("file_ref IS NOT NULL"),
        schema="shiksha_core",
    )
    # Partial-UNIQUE: pro Person nur ein id_front / id_back / passport
    op.create_index(
        "uq_identity_documents_person_kind",
        "identity_documents", ["identity_person_id", "doc_kind"],
        unique=True,
        postgresql_where=sa.text("doc_kind IN ('id_front', 'id_back', 'passport')"),
        schema="shiksha_core",
    )

    # ==================================================================
    # PHASE B.3 — identity_authorizations
    # ==================================================================

    op.create_table(
        "identity_authorizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_org_id",
            sa.Text(),
            sa.ForeignKey("shiksha_core.organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_identity_person_id",
            sa.Integer(),
            sa.ForeignKey("shiksha_core.identity_persons.id", ondelete="CASCADE"),
            nullable=False,
        ),

        # Was darf die Person?
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),

        # Wie wurde authorisiert?
        sa.Column(
            "auth_method", sa.String(30),
            nullable=False, server_default=sa.text("'ausweis_scan'"),
        ),

        # Gültigkeit
        sa.Column(
            "valid_from", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),

        # Widerruf
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "revoked_by_operator_id",
            sa.String(64),
            sa.ForeignKey("shiksha_core.operators.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revoke_reason", sa.Text(), nullable=True),

        # Genehmigung
        sa.Column(
            "granted_by_operator_id",
            sa.String(64),
            sa.ForeignKey("shiksha_core.operators.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column(
            "granted_at", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),

        sa.CheckConstraint(
            "target_type IN ('child', 'booking', 'lesson', 'global')",
            name="ck_identity_authz_target_type",
        ),
        sa.CheckConstraint(
            "auth_method IN ('ausweis_scan', 'passkey_signed', 'manual_override')",
            name="ck_identity_authz_method",
        ),
        sa.CheckConstraint(
            "(target_type = 'global' AND target_id IS NULL) "
            "OR (target_type != 'global' AND target_id IS NOT NULL)",
            name="ck_identity_authz_target_consistency",
        ),
        schema="shiksha_core",
    )

    op.create_index(
        "ix_authz_subject_active",
        "identity_authorizations", ["subject_identity_person_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
        schema="shiksha_core",
    )
    op.create_index(
        "ix_authz_target_active",
        "identity_authorizations", ["target_type", "target_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
        schema="shiksha_core",
    )
    # Index nur auf revoked_at — NOW() darf nicht in Index-Predicate (PG verlangt
    # IMMUTABLE Funktionen). Service-Layer filtert valid_to-Range zur Read-Zeit.
    op.create_index(
        "ix_authz_tenant_active",
        "identity_authorizations", ["tenant_org_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
        schema="shiksha_core",
    )

    # ==================================================================
    # PHASE B.4 — identity_audit_log
    # ==================================================================

    op.create_table(
        "identity_audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "tenant_org_id",
            sa.Text(),
            sa.ForeignKey("shiksha_core.organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_operator_id",
            sa.String(64),
            sa.ForeignKey("shiksha_core.operators.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_kind", sa.String(20),
            nullable=False, server_default=sa.text("'operator'"),
        ),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("target_kind", sa.String(30), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column(
            "details",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),

        sa.CheckConstraint(
            "actor_kind IN ('operator', 'system', 'subject_self')",
            name="ck_audit_actor_kind",
        ),
        schema="shiksha_core",
    )

    op.create_index(
        "ix_audit_target",
        "identity_audit_log", ["target_kind", "target_id"],
        schema="shiksha_core",
    )
    op.create_index(
        "ix_audit_actor_time",
        "identity_audit_log", ["actor_operator_id", sa.text("created_at DESC")],
        schema="shiksha_core",
    )
    op.create_index(
        "ix_audit_tenant_time",
        "identity_audit_log", ["tenant_org_id", sa.text("created_at DESC")],
        schema="shiksha_core",
    )


def downgrade() -> None:
    # PHASE B.4 — identity_audit_log
    op.drop_index("ix_audit_tenant_time", table_name="identity_audit_log", schema="shiksha_core")
    op.drop_index("ix_audit_actor_time", table_name="identity_audit_log", schema="shiksha_core")
    op.drop_index("ix_audit_target", table_name="identity_audit_log", schema="shiksha_core")
    op.drop_table("identity_audit_log", schema="shiksha_core")

    # PHASE B.3 — identity_authorizations
    op.drop_index("ix_authz_tenant_active", table_name="identity_authorizations", schema="shiksha_core")
    op.drop_index("ix_authz_target_active", table_name="identity_authorizations", schema="shiksha_core")
    op.drop_index("ix_authz_subject_active", table_name="identity_authorizations", schema="shiksha_core")
    op.drop_table("identity_authorizations", schema="shiksha_core")

    # PHASE B.2 — identity_documents
    op.drop_index("uq_identity_documents_person_kind", table_name="identity_documents", schema="shiksha_core")
    op.drop_index("ix_identity_documents_file_expiry", table_name="identity_documents", schema="shiksha_core")
    op.drop_index("ix_identity_documents_person", table_name="identity_documents", schema="shiksha_core")
    op.drop_table("identity_documents", schema="shiksha_core")

    # PHASE B.1 — identity_persons
    op.drop_index("ix_identity_persons_linked", table_name="identity_persons", schema="shiksha_core")
    op.drop_index("ix_identity_persons_pending", table_name="identity_persons", schema="shiksha_core")
    op.drop_index("ix_identity_persons_tenant", table_name="identity_persons", schema="shiksha_core")
    op.drop_table("identity_persons", schema="shiksha_core")

    # PHASE A — organizations
    op.drop_constraint(
        "ck_organizations_jurisdiction_format",
        "organizations",
        schema="shiksha_core",
    )
    op.drop_column("organizations", "identity_salt", schema="shiksha_core")
    op.drop_column("organizations", "jurisdiction", schema="shiksha_core")
