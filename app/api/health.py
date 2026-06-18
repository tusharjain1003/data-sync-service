import traceback

from fastapi import APIRouter, Depends
from sqlalchemy import select as sa_select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.collected_status_allowlist import CollectedStatusAllowlist
from app.models.contact import Contact

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/debug/db")
async def debug_db(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    """Diagnostic endpoint — remove before submission."""
    results = {}
    try:
        result = await session.execute(sa_select(1))
        results["ping"] = result.scalar_one()
    except Exception as e:
        results["ping_error"] = f"{type(e).__name__}: {e}"

    try:
        allowlist_result = await session.execute(
            sa_select(CollectedStatusAllowlist).where(
                CollectedStatusAllowlist.canonical_status == "collected"
            )
        )
        row = allowlist_result.scalar_one_or_none()
        results["allowlist_row"] = (
            f"status={row.canonical_status}, counts={row.counts_as_collected}"
            if row else "None"
        )
    except Exception as e:
        results["allowlist_error"] = f"{type(e).__name__}: {e}"

    try:
        stmt = (
            pg_insert(Contact)
            .values(
                source_name="debug_test",
                source_record_id="debug-001",
                email="debug@test.com",
                name="Debug User",
                company="Debug Co",
                source_updated_at=None,
            )
            .on_conflict_do_update(
                index_elements=["source_name", "source_record_id"],
                set_={
                    "email": "debug@test.com",
                    "name": "Debug User",
                    "company": "Debug Co",
                    "source_updated_at": None,
                },
            )
        )
        await session.execute(stmt)
        results["pg_insert"] = "ok"
    except Exception as e:
        results["pg_insert_error"] = f"{type(e).__name__}: {e}"
        results["pg_insert_traceback"] = traceback.format_exc()

    return results
