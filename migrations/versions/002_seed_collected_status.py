"""Seed collected_status_allowlist with initial canonical statuses.

Revision ID: 002
Revises: 001
Create Date: 2026-06-18
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy import Boolean, String, column, table

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

allowlist_table = table(
    "collected_status_allowlist",
    column("canonical_status", String),
    column("counts_as_collected", Boolean),
)


def upgrade() -> None:
    op.bulk_insert(
        allowlist_table,
        [
            {"canonical_status": "collected", "counts_as_collected": True},
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM collected_status_allowlist WHERE canonical_status = 'collected'"
    )
