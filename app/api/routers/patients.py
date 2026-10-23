from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.deps import NowDep, SessionDep
from app.models import Patient
from app.schemas import AppointmentRead, PatientCreate, PatientRead
from app.services import booking
from app.services import patients as patient_service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientRead], summary="List registered patients")
async def list_patients(session: SessionDep) -> list[Patient]:
    result = await session.execute(select(Patient).order_by(Patient.name))
    return list(result.scalars().all())


@router.post(
    "",
    response_model=PatientRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a patient",
    responses={
        409: {
            "description": "Email already registered; the existing patient's id is in "
            "error.details.patient_id"
        }
    },
)
async def create_patient(payload: PatientCreate, session: SessionDep) -> Patient:
    return await patient_service.create_patient(
        session, name=payload.name, email=payload.email, phone=payload.phone
    )


@router.get(
    "/lookup",
    response_model=PatientRead,
    summary="Find a patient by email",
    responses={404: {"description": "No patient with that email"}},
)
async def lookup_patient(
    session: SessionDep,
    email: str = Query(description="The email the patient registered with"),
) -> Patient:
    return await patient_service.get_patient_by_email(session, email)


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
