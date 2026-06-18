"""Idempotent seed for collected_status_allowlist.

Ensures the canonical seed row exists on every upgrade by using
INSERT ... ON CONFLICT DO NOTHING.  Safe to re-run — no error if the
row already exists from migration 002 or from manual insertion.

Revision ID: 003
Revises: 002
Create Date: 2026-06-19
"""
from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO collected_status_allowlist (canonical_status, counts_as_collected) "
        "VALUES ('collected', true) "
        "ON CONFLICT (canonical_status) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM collected_status_allowlist WHERE canonical_status = 'collected'"
    )
