"""Demo-only endpoints for simulating failure scenarios and seeding data."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MessageResponse
from app.connectors.registry import (
    list_known_sources,
    reset_simulations,
    set_simulation,
)
from app.core.database import get_session
from app.services.seed import seed_demo_data

router = APIRouter(prefix="/demo", tags=["demo"])


class SeedResponse(BaseModel):
    message: str
    contacts: int
    events: int
    transactions: int


@router.post("/seed", response_model=SeedResponse)
async def demo_seed(session: AsyncSession = Depends(get_session)) -> SeedResponse:
    """Seed deterministic demo data into the database.

    Safe to call multiple times — uses idempotent upserts.
    """
    summary = await seed_demo_data(session)
    return SeedResponse(
        message="Demo data seeded successfully.",
        **summary,
    )


@router.post("/simulate-cursor-expired/{source_name}", response_model=MessageResponse)
async def simulate_cursor_expired(source_name: str) -> MessageResponse:
    try:
        set_simulation(source_name, "cursor_expired")
    except ValueError:
        known = ", ".join(list_known_sources())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source '{source_name}'. Known sources: {known}",
        )
    return MessageResponse(
        message=f"Simulation 'cursor_expired' activated for '{source_name}'. "
        f"The next sync will fall back from incremental to full fetch."
    )


@router.post("/simulate-source-failure/{source_name}", response_model=MessageResponse)
async def simulate_source_failure(source_name: str) -> MessageResponse:
    try:
        set_simulation(source_name, "source_unavailable")
    except ValueError:
        known = ", ".join(list_known_sources())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source '{source_name}'. Known sources: {known}",
        )
    return MessageResponse(
        message=f"Simulation 'source_unavailable' activated for '{source_name}'. "
        f"The next sync will fail for this source."
    )


@router.post("/reset-simulations", response_model=MessageResponse)
async def demo_reset_simulations() -> MessageResponse:
    reset_simulations()
    return MessageResponse(message="All simulation overrides have been cleared.")
