from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import NowDep, SessionDep
from app.schemas import AppointmentCreate, AppointmentRead, CancelRequest, RescheduleRequest
from app.services import booking

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post(
    "",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Book a slot",
    responses={
        400: {"description": "Outside working hours, in the past, misaligned, or too soon"},
        404: {"description": "Unknown doctor or patient"},
        409: {"description": "Slot already taken"},
    },
)
async def create_appointment(
    payload: AppointmentCreate, response: Response, session: SessionDep, now: NowDep
) -> object:
    appointment = await booking.create_appointment(
        session,
        doctor_id=payload.doctor_id,
        patient_id=payload.patient_id,
        starts_at=payload.starts_at,
        now=now,
    )
    response.headers["Location"] = f"/appointments/{appointment.id}"
    return appointment


@router.get("/{appointment_id}", response_model=AppointmentRead, summary="Read one appointment")
async def read_appointment(appointment_id: uuid.UUID, session: SessionDep) -> object:
    return await booking.get_appointment(session, appointment_id)


@router.patch(
    "/{appointment_id}/cancel",
    response_model=AppointmentRead,
    summary="Cancel an appointment with a reason",
    responses={
        404: {"description": "Unknown appointment"},
        409: {"description": "Already cancelled"},
    },
)
async def cancel_appointment(
    appointment_id: uuid.UUID, payload: CancelRequest, session: SessionDep, now: NowDep
) -> object:
    return await booking.cancel_appointment(
        session, appointment_id=appointment_id, reason=payload.reason, now=now
    )


@router.patch(
    "/{appointment_id}/reschedule",
    response_model=AppointmentRead,
    summary="Move an appointment to another slot",
    responses={
        400: {"description": "New slot fails booking validation"},
        404: {"description": "Unknown appointment"},
        409: {"description": "Appointment cancelled, or the new slot is taken"},
    },
)
async def reschedule_appointment(
    appointment_id: uuid.UUID, payload: RescheduleRequest, session: SessionDep, now: NowDep
) -> object:
    return await booking.reschedule_appointment(
        session, appointment_id=appointment_id, starts_at=payload.starts_at, now=now
    )
