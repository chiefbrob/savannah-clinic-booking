"""Patient registration and lookup.

The clinic's front desk creates a patient once; the booking flow then reuses the
record by email. Registration is deliberately separate from booking so a person
can exist as a patient before they have an appointment — and so a returning
patient is not duplicated every time they book.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.models import Patient


def normalise_email(email: str) -> str:
    return email.strip().lower()


async def find_patient_by_email(session: AsyncSession, email: str) -> Patient | None:
    result = await session.execute(select(Patient).where(Patient.email == normalise_email(email)))
    return result.scalar_one_or_none()


async def get_patient_by_email(session: AsyncSession, email: str) -> Patient:
    patient = await find_patient_by_email(session, email)
    if patient is None:
        raise NotFound(
            "No patient is registered with that email address.",
            code="patient_not_found",
            details={"email": normalise_email(email)},
        )
    return patient


async def create_patient(
    session: AsyncSession,
    *,
    name: str,
    email: str,
    phone: str | None = None,
) -> Patient:
    address = normalise_email(email)
    existing = await find_patient_by_email(session, address)
    if existing is not None:
        raise Conflict(
            "A patient with that email is already registered.",
            code="patient_email_taken",
            details={"patient_id": str(existing.id), "email": address},
        )

    patient = Patient(name=name, email=address, phone=phone or None)
    session.add(patient)
    await session.commit()
    await session.refresh(patient)
    return patient
