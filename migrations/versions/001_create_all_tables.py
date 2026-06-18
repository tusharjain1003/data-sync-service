"""Create all core tables.

Revision ID: 001
Revises: None
Create Date: 2026-06-18
"""
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _created_at() -> Any:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _updated_at() -> Any:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "source_connections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(255), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("cursor_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_full_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_incremental_sync_at", sa.DateTime(timezone=True), nullable=True
        ),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_name", name="uq_source_connections_name"),
    )

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("summary", JSONB(), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sync_run_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sync_run_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("sync_mode", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column(
            "records_seen", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "records_upserted",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "records_rejected",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["sync_run_id"], ["sync_runs.id"], name="fk_sync_run_sources_run"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "external_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=False),
        sa.Column("record_type", sa.String(255), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_name",
            "source_record_id",
            "record_type",
            name="uq_external_records_source",
        ),
    )

    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_name", "source_record_id", name="uq_contacts_source"
        ),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attendee_emails", JSONB(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_name", "source_record_id", name="uq_events_source"
        ),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=False),
        sa.Column("customer_email", sa.String(320), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("canonical_status", sa.String(50), nullable=False),
        sa.Column("source_status", sa.String(100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_name", "source_record_id", name="uq_transactions_source"
        ),
    )

    op.create_table(
        "collected_status_allowlist",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canonical_status", sa.String(50), nullable=False),
        sa.Column(
            "counts_as_collected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_status", name="uq_allowlist_status"),
    )


def downgrade() -> None:
    op.drop_table("collected_status_allowlist")
    op.drop_table("transactions")
    op.drop_table("events")
    op.drop_table("contacts")
    op.drop_table("external_records")
    op.drop_table("sync_run_sources")
    op.drop_table("sync_runs")
    op.drop_table("source_connections")
