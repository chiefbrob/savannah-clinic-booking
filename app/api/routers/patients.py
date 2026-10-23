from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import NowDep, SessionDep
from app.models import Patient
from app.schemas import AppointmentRead, PatientRead
from app.services import booking

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientRead], summary="List registered patients")
async def list_patients(session: SessionDep) -> list[Patient]:
    result = await session.execute(select(Patient).order_by(Patient.name))
    return list(result.scalars().all())


@router.get("/{patient_id}", response_model=PatientRead, summary="Get one patient")
async def read_patient(patient_id: uuid.UUID, session: SessionDep) -> Patient:
    return await booking.get_patient(session, patient_id)


@router.get(
    "/{patient_id}/appointments",
    response_model=list[AppointmentRead],
    summary="Upcoming appointments for a patient, soonest first",
    responses={404: {"description": "Unknown patient"}},
)
async def list_appointments(
    patient_id: uuid.UUID,
    session: SessionDep,
    now: NowDep,
    include_past: bool = Query(
        default=False,
        description="Include past and cancelled appointments instead of only upcoming ones.",
    ),
) -> list[object]:
    return await booking.list_patient_appointments(
        session, patient_id=patient_id, now=now, include_past=include_past
    )
