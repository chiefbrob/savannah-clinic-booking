from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness and database check")
async def health(session: SessionDep) -> HealthResponse:
    settings = get_settings()
    database = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - only when the DB is down
        database = "unavailable"
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        database=database,
        version=settings.app_version,
        timezone=settings.clinic_timezone,
    )
