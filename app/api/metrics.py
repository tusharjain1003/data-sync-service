"""Revenue metrics API endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.metrics import get_revenue_breakdown, get_revenue_summary

router = APIRouter(prefix="/metrics", tags=["metrics"])


class RevenueSummaryItem(BaseModel):
    currency: str
    total_amount_minor: int


class RevenueSummaryResponse(BaseModel):
    start: date
    end: date
    items: list[RevenueSummaryItem]


class RevenueBreakdownItem(BaseModel):
    date: str
    currency: str
    amount_minor: int


class RevenueBreakdownResponse(BaseModel):
    start: date
    end: date
    interval: str
    items: list[RevenueBreakdownItem]


@router.get("/revenue/summary", response_model=RevenueSummaryResponse)
async def revenue_summary(
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(..., description="End date (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_session),
) -> RevenueSummaryResponse:
    try:
        rows = await get_revenue_summary(session, start, end)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    items = [
        RevenueSummaryItem(currency=r.currency, total_amount_minor=r.total_amount_minor)
        for r in rows
    ]
    return RevenueSummaryResponse(start=start, end=end, items=items)


@router.get("/revenue/breakdown", response_model=RevenueBreakdownResponse)
async def revenue_breakdown(
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(..., description="End date (YYYY-MM-DD)"),
    interval: str = Query("day", description="Breakdown interval (day)"),
    session: AsyncSession = Depends(get_session),
) -> RevenueBreakdownResponse:
    try:
        rows = await get_revenue_breakdown(session, start, end, interval)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    items = [
        RevenueBreakdownItem(date=r.date, currency=r.currency, amount_minor=r.amount_minor)
        for r in rows
    ]
    return RevenueBreakdownResponse(start=start, end=end, interval=interval, items=items)
