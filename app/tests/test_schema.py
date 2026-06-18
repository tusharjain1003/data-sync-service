"""Model schema verification tests.

These tests verify that SQLAlchemy model metadata (table names, columns,
constraints) match the expected schema without requiring a live database.
"""

from typing import Any

from sqlalchemy import UniqueConstraint

from app.models import (
    CollectedStatusAllowlist,
    Contact,
    Event,
    ExternalRecord,
    SourceConnection,
    SyncRun,
    SyncRunSource,
    Transaction,
)


def _unique_constraint_cols(
    table: Any, model_cls: Any,
) -> list[set[str]]:
    """Return the set of column names for each unique constraint on *table*."""
    return [
        {c.name for c in uq.columns}
        for uq in table.constraints
        if isinstance(uq, UniqueConstraint)
        and uq.columns
    ]


def test_all_models_registered() -> None:
    from app.models import Base

    expected = {
        "source_connections",
        "sync_runs",
        "sync_run_sources",
        "external_records",
        "contacts",
        "events",
        "transactions",
        "collected_status_allowlist",
    }
    table_names = set(Base.metadata.tables.keys())
    missing = expected - table_names
    assert not missing, f"Missing tables: {missing}"


def test_source_connection_columns() -> None:
    table = SourceConnection.__table__
    cols = {c.name: c for c in table.columns}
    assert cols["id"].primary_key
    assert cols["source_name"].unique
    assert not cols["source_name"].nullable
    assert cols["cursor"].nullable


def test_sync_run_columns() -> None:
    table = SyncRun.__table__
    cols = {c.name: c for c in table.columns}
    assert cols["id"].primary_key
    assert cols["started_at"].nullable is False
    assert cols["status"].nullable is False
    assert cols["completed_at"].nullable


def test_sync_run_source_columns() -> None:
    table = SyncRunSource.__table__
    cols = {c.name: c for c in table.columns}
    assert cols["sync_run_id"].foreign_keys
    assert cols["records_seen"].default


def test_external_record_unique_constraint() -> None:
    table = ExternalRecord.__table__
    col_sets = _unique_constraint_cols(table, ExternalRecord)
    assert {"source_name", "source_record_id", "record_type"} in col_sets, (
        "Missing unique constraint on (source_name, source_record_id, record_type)"
    )


def test_contact_unique_constraint() -> None:
    table = Contact.__table__
    col_sets = _unique_constraint_cols(table, Contact)
    assert {"source_name", "source_record_id"} in col_sets, (
        "Missing unique constraint on (source_name, source_record_id)"
    )


def test_event_unique_constraint() -> None:
    table = Event.__table__
    col_sets = _unique_constraint_cols(table, Event)
    assert {"source_name", "source_record_id"} in col_sets, (
        "Missing unique constraint on (source_name, source_record_id)"
    )


def test_transaction_columns() -> None:
    table = Transaction.__table__
    cols = {c.name: c for c in table.columns}
    assert cols["amount_minor"].nullable is False
    assert cols["canonical_status"].nullable is False
    assert cols["source_status"].nullable is False
    col_sets = _unique_constraint_cols(table, Transaction)
    assert {"source_name", "source_record_id"} in col_sets, (
        "Missing unique constraint on (source_name, source_record_id)"
    )


def test_collected_status_allowlist() -> None:
    table = CollectedStatusAllowlist.__table__
    cols = {c.name: c for c in table.columns}
    assert cols["canonical_status"].unique
    assert cols["canonical_status"].nullable is False
    assert cols["counts_as_collected"].nullable is False


def test_external_record_uses_ingested_at() -> None:
    """Verify the ORM column name matches the migration column name."""
    cols = ExternalRecord.__table__.columns
    assert "ingested_at" in cols, "ExternalRecord must have ingested_at column"
    assert "created_at" not in cols, (
        "ExternalRecord must not use created_at; "
        "migration and ORM metadata must agree"
    )


def test_jsonb_columns_exist() -> None:
    """Verify tables that must use JSONB have it declared."""
    from sqlalchemy.dialects.postgresql import JSONB

    sync_run_cols = SyncRun.__table__.columns
    assert isinstance(sync_run_cols["summary"].type, JSONB)

    external_cols = ExternalRecord.__table__.columns
    assert isinstance(external_cols["payload"].type, JSONB)

    event_cols = Event.__table__.columns
    assert isinstance(event_cols["attendee_emails"].type, JSONB)


def test_all_tables_created_in_sqlite(sqla_engine: Any) -> None:
    """Verify DDL compiles and all tables are created in SQLite."""
    from sqlalchemy import inspect

    inspector = inspect(sqla_engine)
    table_names = inspector.get_table_names()

    expected = {
        "source_connections",
        "sync_runs",
        "sync_run_sources",
        "external_records",
        "contacts",
        "events",
        "transactions",
        "collected_status_allowlist",
    }
    missing = expected - set(table_names)
    assert not missing, f"Tables missing after create_all: {missing}"


def test_migration_smoke(tmp_path: Any) -> None:
    """Run Alembic migrations against a fresh SQLite DB and verify the result.

    This is a migration smoke test that runs the actual Alembic upgrade to
    *head* (not ``Base.metadata.create_all``) so that any drift between the
    migration scripts and the ORM model is detected.
    """
    import alembic.command
    import alembic.config
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import Session

    from app.core.config import settings
    from app.models.external_record import ExternalRecord

    db_path = tmp_path / "migration_test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    original = settings.database_url
    settings.database_url = db_url
    try:
        cfg = alembic.config.Config("alembic.ini")
        alembic.command.upgrade(cfg, "head")

        # --- Inspect via sync engine (same file) ---
        sync_url = f"sqlite:///{db_path}"
        engine = create_engine(sync_url)
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())

        expected_tables = {
            "source_connections",
            "sync_runs",
            "sync_run_sources",
            "external_records",
            "contacts",
            "events",
            "transactions",
            "collected_status_allowlist",
        }
        missing = expected_tables - table_names
        assert not missing, f"Tables missing after Alembic upgrade: {missing}"

        # --- Verify external_records columns match the ORM ---
        db_cols = {c["name"] for c in inspector.get_columns("external_records")}
        orm_cols = set(ExternalRecord.__table__.columns.keys())
        assert db_cols == orm_cols, (
            f"external_records column mismatch:\n"
            f"  DB  columns: {sorted(db_cols)}\n"
            f"  ORM columns: {sorted(orm_cols)}"
        )
        assert "ingested_at" in db_cols
        assert "created_at" not in db_cols

        # --- Verify seed row in collected_status_allowlist ---
        with Session(engine) as session:
            rows = session.execute(
                text(
                    "SELECT canonical_status, counts_as_collected "
                    "FROM collected_status_allowlist"
                )
            ).all()
            assert len(rows) == 1, (
                f"Expected 1 seed row, got {len(rows)}"
            )
            assert rows[0][0] == "collected"
            # SQLite stores bool as 0/1; accept both
            assert rows[0][1] in (True, 1), (
                f"counts_as_collected should be truthy, got {rows[0][1]!r}"
            )
    finally:
        settings.database_url = original
