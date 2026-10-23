from __future__ import annotations

import uuid
from datetime import date as date_type

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import NowDep, SessionDep
from app.core.config import get_settings
from app.models import Doctor
from app.schemas import AvailabilityResponse, DoctorRead, SlotRead
from app.services import availability as availability_service
from app.services.booking import get_doctor

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=list[DoctorRead], summary="List the clinic's doctors")
async def list_doctors(session: SessionDep) -> list[Doctor]:
    result = await session.execute(select(Doctor).order_by(Doctor.name))
    return list(result.scalars().all())


@router.get("/{doctor_id}", response_model=DoctorRead, summary="Get one doctor")
async def read_doctor(doctor_id: uuid.UUID, session: SessionDep) -> Doctor:
    return await get_doctor(session, doctor_id)


@router.get(
    "/{doctor_id}/availability",
    response_model=AvailabilityResponse,
    summary="Free 30-minute slots for a doctor on a date",
    response_description="Scheduled slots, excluding booked, past, and too-soon slots",
)
async def read_availability(
    doctor_id: uuid.UUID,
    session: SessionDep,
    now: NowDep,
    day: date_type | None = Query(
        default=None,
        alias="date",
        description="Local calendar date (YYYY-MM-DD) in the doctor's timezone. Defaults to today.",
    ),
) -> AvailabilityResponse:
    doctor = await get_doctor(session, doctor_id)
    settings = get_settings()
    tz = availability_service.doctor_timezone(doctor)
    target_day = day or now.astimezone(tz).date()

    slots = await availability_service.available_slots(session, doctor, target_day, now=now)
    return AvailabilityResponse(
        doctor_id=doctor.id,
        date=target_day,
        timezone=str(tz),
        slot_minutes=settings.slot_minutes,
        slots=[SlotRead(starts_at=slot.starts_at, ends_at=slot.ends_at) for slot in slots],
    )
