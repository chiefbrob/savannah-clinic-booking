"""Booking, cancelling and rescheduling.

The hard part is not validating a slot — it is guaranteeing that two requests
racing for the same slot cannot both win. That guarantee is delegated to
``ix_appointments_no_double_booking`` (a partial unique index in Postgres).
The code below validates everything it can *before* touching the database, then
treats a unique-violation as the authoritative "slot already taken" signal.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc, to_utc
from app.core.config import get_settings
from app.core.errors import BadRequest, Conflict, NotFound
from app.models import BOOKED, CANCELLED, COMPLETED, Appointment, Doctor, Patient
from app.services.availability import Slot, available_slots, working_slots

DOUBLE_BOOKING_INDEX = "ix_appointments_no_double_booking"


async def get_doctor(session: AsyncSession, doctor_id: uuid.UUID) -> Doctor:
    doctor = await session.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFound(
            "Doctor not found.",
            code="doctor_not_found",
            details={"doctor_id": str(doctor_id)},
        )
    return doctor


async def get_patient(session: AsyncSession, patient_id: uuid.UUID) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None:
        raise NotFound(
            "Patient not found.",
            code="patient_not_found",
            details={"patient_id": str(patient_id)},
        )
    return patient


async def get_appointment(session: AsyncSession, appointment_id: uuid.UUID) -> Appointment:
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise NotFound(
            "Appointment not found.",
            code="appointment_not_found",
            details={"appointment_id": str(appointment_id)},
        )
    return appointment


async def _validate_target_slot(
    session: AsyncSession,
    doctor: Doctor,
    starts_at: datetime,
    now: datetime,
) -> Slot:
    """Apply every rule a fresh booking must satisfy; return the matched slot."""
    settings = get_settings()
    tz: ZoneInfo = ZoneInfo(doctor.timezone or settings.clinic_timezone)
    local = starts_at.astimezone(tz)

    if local.minute % settings.slot_minutes or local.second or local.microsecond:
        raise BadRequest(
            f"Slots start on {settings.slot_minutes}-minute boundaries.",
            code="slot_not_aligned",
            details={
                "starts_at": local.isoformat(),
                "slot_minutes": settings.slot_minutes,
                "hint": "round the start time to :00 or :30",
            },
        )

    slots = await working_slots(session, doctor, local.date())
    match = next((slot for slot in slots if slot.starts_at == starts_at), None)
    if match is None:
        raise BadRequest(
            f"{doctor.name} does not work at {local.strftime('%H:%M')} on "
            f"{local.strftime('%A %d %B %Y')}.",
            code="outside_working_hours",
            details={
                "starts_at": local.isoformat(),
                "weekday": local.strftime("%A"),
                "doctor_id": str(doctor.id),
            },
        )

    if starts_at <= now:
        raise BadRequest(
            "Appointments cannot be booked in the past.",
            code="appointment_in_past",
            details={"starts_at": local.isoformat(), "now": now.astimezone(tz).isoformat()},
        )

    earliest = now + timedelta(minutes=settings.min_booking_lead_minutes)
    if starts_at < earliest:
        raise BadRequest(
            f"Appointments must be booked at least {settings.min_booking_lead_minutes} "
            "minutes in advance.",
            code="booking_too_soon",
            details={
                "starts_at": local.isoformat(),
                "min_lead_minutes": settings.min_booking_lead_minutes,
                "earliest_bookable": earliest.astimezone(tz).isoformat(),
            },
        )

    return match


def _is_double_booking(exc: IntegrityError) -> bool:
    return DOUBLE_BOOKING_INDEX in str(exc.orig)


async def create_appointment(
    session: AsyncSession,
    *,
    doctor_id: uuid.UUID,
    patient_id: uuid.UUID,
    starts_at: datetime,
    now: datetime | None = None,
) -> Appointment:
    now = now or now_utc()
    starts_utc = to_utc(starts_at)

    doctor = await get_doctor(session, doctor_id)
    await get_patient(session, patient_id)
    slot = await _validate_target_slot(session, doctor, starts_utc, now)
    # Read attributes now: a rollback below would expire the instance.
    doctor_pk = doctor.id

    appointment = Appointment(
        doctor_id=doctor.id,
        patient_id=patient_id,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        status=BOOKED,
    )
    session.add(appointment)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_double_booking(exc):
            raise Conflict(
                "That slot was just booked by someone else. Pick another slot.",
                code="slot_taken",
                details={
                    "doctor_id": str(doctor_pk),
                    "starts_at": starts_utc.isoformat(),
                },
            ) from exc
        raise

    await session.commit()
    await session.refresh(appointment)
    return appointment


async def cancel_appointment(
    session: AsyncSession,
    *,
    appointment_id: uuid.UUID,
    reason: str,
    now: datetime | None = None,
) -> Appointment:
    now = now or now_utc()
    appointment = await get_appointment(session, appointment_id)

    if appointment.status == CANCELLED:
        raise Conflict(
            "This appointment is already cancelled.",
            code="appointment_already_cancelled",
            details={
                "appointment_id": str(appointment.id),
                "cancelled_at": appointment.cancelled_at.isoformat()
                if appointment.cancelled_at
                else None,
            },
        )
    if appointment.status == COMPLETED:
        raise Conflict(
            "A completed appointment cannot be cancelled.",
            code="appointment_not_cancellable",
            details={"appointment_id": str(appointment.id), "status": appointment.status},
        )

    appointment.status = CANCELLED
    appointment.cancel_reason = reason
    appointment.cancelled_at = now
    await session.commit()
    await session.refresh(appointment)
    return appointment


async def reschedule_appointment(
    session: AsyncSession,
    *,
    appointment_id: uuid.UUID,
    starts_at: datetime,
    now: datetime | None = None,
) -> Appointment:
    now = now or now_utc()
    starts_utc = to_utc(starts_at)

    appointment = await get_appointment(session, appointment_id)
    if appointment.status == CANCELLED:
        raise Conflict(
            "A cancelled appointment cannot be rescheduled. Book a new one instead.",
            code="appointment_cancelled",
            details={"appointment_id": str(appointment.id)},
        )
    if appointment.status == COMPLETED:
        raise Conflict(
            "A completed appointment cannot be rescheduled.",
            code="appointment_not_reschedulable",
            details={"appointment_id": str(appointment.id), "status": appointment.status},
        )

    doctor = await get_doctor(session, appointment.doctor_id)
    slot = await _validate_target_slot(session, doctor, starts_utc, now)
    doctor_pk = doctor.id

    if appointment.starts_at == slot.starts_at:
        return appointment

    # One statement moves the appointment: the old slot leaves the partial
    # unique index and the new one enters it in the same transaction, so there
    # is no window in which the patient holds both slots or neither.
    appointment.starts_at = slot.starts_at
    appointment.ends_at = slot.ends_at
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_double_booking(exc):
            raise Conflict(
                "The requested slot is already booked. The original slot was kept.",
                code="slot_taken",
                details={
                    "appointment_id": str(appointment_id),
                    "doctor_id": str(doctor_pk),
                    "starts_at": starts_utc.isoformat(),
                },
            ) from exc
        raise

    await session.commit()
    await session.refresh(appointment)
    return appointment


async def list_patient_appointments(
    session: AsyncSession,
    *,
    patient_id: uuid.UUID,
    now: datetime | None = None,
    include_past: bool = False,
) -> list[Appointment]:
    now = now or now_utc()
    await get_patient(session, patient_id)

    stmt = select(Appointment).where(Appointment.patient_id == patient_id)
    if not include_past:
        stmt = stmt.where(
            Appointment.status == BOOKED,
            Appointment.starts_at >= now,
        )
    stmt = stmt.order_by(Appointment.starts_at.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


__all__ = [
    "available_slots",
    "cancel_appointment",
    "create_appointment",
    "get_appointment",
    "get_doctor",
    "get_patient",
    "list_patient_appointments",
    "reschedule_appointment",
]
