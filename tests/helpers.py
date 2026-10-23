"""Testing helpers: pinned clock, timezone-aware constructors, data builders."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Doctor, DoctorSchedule, Patient

CLINIC_TZ = ZoneInfo("Africa/Nairobi")  # UTC+3, no DST
UTC = timezone.utc

# Monday 2 November 2026, 12:00 in Nairobi. Everything is relative to this.
FIXED_NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
TODAY = FIXED_NOW.astimezone(CLINIC_TZ).date()  # 2026-11-02 (Monday)

MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
WEEKDAYS = (MON, TUE, WED, THU, FRI)


def next_weekday(start: date, weekday: int) -> date:
    """The next occurrence of ``weekday`` strictly after ``start``."""
    delta = (weekday - start.weekday()) % 7 or 7
    return start + timedelta(days=delta)


def previous_weekday(start: date, weekday: int) -> date:
    delta = (start.weekday() - weekday) % 7 or 7
    return start - timedelta(days=delta)


def at(day: date, hhmm: str, tz: ZoneInfo = CLINIC_TZ) -> datetime:
    hours, minutes = (int(part) for part in hhmm.split(":"))
    return datetime.combine(day, time(hours, minutes), tzinfo=tz)


def iso(moment: datetime) -> str:
    return moment.isoformat()


async def make_doctor(
    session: AsyncSession,
    *,
    name: str = "Dr Test",
    email: str = "dr.test@clinic.example",
    windows: list[tuple[int, str, str]] | None = None,
) -> Doctor:
    windows = windows if windows is not None else [(day, "08:00", "16:00") for day in WEEKDAYS]
    doctor = Doctor(name=name, specialty="General Practice", email=email, timezone="Africa/Nairobi")
    session.add(doctor)
    await session.flush()
    for weekday, start, end in windows:
        session.add(
            DoctorSchedule(
                doctor_id=doctor.id,
                weekday=weekday,
                start_time=time(*map(int, start.split(":"))),
                end_time=time(*map(int, end.split(":"))),
            )
        )
    await session.commit()
    return doctor


async def make_patient(
    session: AsyncSession, *, name: str = "Test Patient", email: str = "patient@example.com"
) -> Patient:
    patient = Patient(name=name, email=email, phone="+254700000000")
    session.add(patient)
    await session.commit()
    return patient


def booking_payload(doctor_id, patient_id, moment: datetime) -> dict[str, str]:
    return {
        "doctor_id": str(doctor_id),
        "patient_id": str(patient_id),
        "starts_at": iso(moment),
    }


def parse_iso(value: str) -> datetime:
    """Parse an API timestamp. Pydantic emits ``Z``; Python 3.10 does not accept it."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
