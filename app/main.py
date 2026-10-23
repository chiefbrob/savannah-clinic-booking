"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routers import appointments, doctors, health, patients
from app.core.config import get_settings
from app.core.db import engine
from app.core.errors import AppError

logger = logging.getLogger("clinic")

DESCRIPTION = """
Booking API for a small clinic: 5 doctors, 30-minute slots, working hours per
doctor, and no two patients ever holding the same slot.

**How double-booking is prevented.** The database enforces it with a *partial
unique index* on `(doctor_id, starts_at)` restricted to rows whose status is
`booked`. Cancelling flips the status, which frees the slot atomically; the
application never has to "check then insert" and therefore cannot lose a race.

Times are returned in UTC. Working hours are interpreted in the clinic
timezone (`Africa/Nairobi`), so slot generation is wall-clock based.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "starting %s v%s (env=%s, tz=%s)",
        settings.app_name,
        settings.app_version,
        settings.environment,
        settings.clinic_timezone,
    )
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        lifespan=lifespan,
        contact={"name": "Brian Obare", "url": "https://github.com/chiefbrob"},
        license_info={"name": "MIT"},
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # ``exc.errors()`` can carry a ValueError instance under "ctx", which is
        # not JSON serialisable; stringify those before responding.
        fields = []
        for error in exc.errors():
            entry = dict(error)
            if "ctx" in entry:
                entry["ctx"] = {key: str(value) for key, value in entry["ctx"].items()}
            fields.append(entry)
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request body or parameters are invalid.",
                    "details": {"fields": fields},
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized"}
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": codes.get(exc.status_code, "http_error"),
                    "message": str(exc.detail),
                    "details": {},
                }
            },
            headers=getattr(exc, "headers", None),
        )

    app.include_router(health.router)
    app.include_router(doctors.router)
    app.include_router(appointments.router)
    app.include_router(patients.router)

    # The booking UI is served by nginx from ./docs in production; mounting it
    # here as well keeps `uvicorn app.main:app` a complete local environment.
    # API routes are registered first, so they always win.
    web_dir = Path(__file__).resolve().parent.parent / "docs"
    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="app")

    return app


app = create_app()
