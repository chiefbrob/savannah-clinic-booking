"""Availability: turning working hours into bookable 30-minute slots.

Slots are derived, never stored. A slot exists if:

1. it falls inside one of the doctor's working windows for that weekday,
2. it starts on a slot boundary,
3. it is not already booked by an active appointment, and
4. it is at least the configured lead time away.

Because nothing is materialised there is no drift to reconcile when a doctor's
hours change, and no "stale slot" cleanup job.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import UTC, now_utc, wall_clock
from app.core.config import get_settings
from app.models import BOOKED, Appointment, Doctor, DoctorSchedule


@dataclass(frozen=True)
class Slot:
    starts_at: datetime
    ends_at: datetime


def doctor_timezone(doctor: Doctor) -> ZoneInfo:
    return ZoneInfo(doctor.timezone or get_settings().clinic_timezone)


def build_slots(
    schedules: list[DoctorSchedule],
    day: date,
    tz: ZoneInfo,
    slot_minutes: int,
) -> list[Slot]:
    """Expand working windows into half-open slots, de-duplicated and sorted."""
    slots: dict[datetime, Slot] = {}
    for schedule in schedules:
        cursor = wall_clock(day, schedule.start_time, tz)
        window_end = wall_clock(day, schedule.end_time, tz)
        step = timedelta(minutes=slot_minutes)
        while cursor + step <= window_end:
            start_utc = cursor.astimezone(UTC)
            slots[start_utc] = Slot(starts_at=start_utc, ends_at=(cursor + step).astimezone(UTC))
            cursor = cursor + step
    return sorted(slots.values(), key=lambda slot: slot.starts_at)


async def schedules_for_weekday(
    session: AsyncSession, doctor_id, weekday: int
) -> list[DoctorSchedule]:
    result = await session.execute(
        select(DoctorSchedule)
        .where(DoctorSchedule.doctor_id == doctor_id, DoctorSchedule.weekday == weekday)
        .order_by(DoctorSchedule.start_time)
    )
    return list(result.scalars().all())


async def _schedules_by_weekday(
    session: AsyncSession, doctor_id
) -> dict[int, list[DoctorSchedule]]:
    result = await session.execute(
        select(DoctorSchedule)
        .where(DoctorSchedule.doctor_id == doctor_id)
        .order_by(DoctorSchedule.weekday, DoctorSchedule.start_time)
    )
    grouped: dict[int, list[DoctorSchedule]] = {}
    for schedule in result.scalars().all():
        grouped.setdefault(schedule.weekday, []).append(schedule)
    return grouped


async def booked_starts(
    session: AsyncSession, doctor_id, start_utc: datetime, end_utc: datetime
) -> set[datetime]:
    result = await session.execute(
        select(Appointment.starts_at).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == BOOKED,
            Appointment.starts_at >= start_utc,
            Appointment.starts_at < end_utc,
        )
    )
    return {instant.astimezone(UTC) for instant in result.scalars().all()}


async def working_slots(session: AsyncSession, doctor: Doctor, day: date) -> list[Slot]:
    """Every slot the doctor is scheduled for on ``day``, ignoring bookings."""
    settings = get_settings()
    tz = doctor_timezone(doctor)
    schedules = await schedules_for_weekday(session, doctor.id, day.weekday())
    return build_slots(schedules, day, tz, settings.slot_minutes)


async def availability_range(
    session: AsyncSession,
    doctor: Doctor,
    start_day: date,
    days: int,
    now: datetime | None = None,
) -> list[tuple[date, list[Slot]]]:
    """Free slots per day across a window — two queries regardless of window size.

    The per-day endpoint and the calendar summary both use this, so the two can
    never disagree about what "free" means.
    """
    settings = get_settings()
    now = now or now_utc()
    tz = doctor_timezone(doctor)
    earliest = now + timedelta(minutes=settings.min_booking_lead_minutes)

    schedules = await _schedules_by_weekday(session, doctor.id)
    last_day = start_day + timedelta(days=days - 1)
    window_start = wall_clock(start_day, time(0, 0), tz).astimezone(UTC)
    window_end = wall_clock(last_day + timedelta(days=1), time(0, 0), tz).astimezone(UTC)
    booked = await booked_starts(session, doctor.id, window_start, window_end)

    result: list[tuple[date, list[Slot]]] = []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        slots = build_slots(schedules.get(day.weekday(), []), day, tz, settings.slot_minutes)
        free = [
            slot for slot in slots if slot.starts_at not in booked and slot.starts_at >= earliest
        ]
        result.append((day, free))
    return result


async def available_slots(
    session: AsyncSession, doctor: Doctor, day: date, now: datetime | None = None
) -> list[Slot]:
    """Bookable slots: scheduled, unbooked, and far enough in the future."""
    return (await availability_range(session, doctor, day, 1, now=now))[0][1]


async def next_available(
    session: AsyncSession, doctor: Doctor, now: datetime | None = None, days: int = 14
) -> Slot | None:
    """The soonest bookable slot, or ``None`` if the window is fully booked."""
    now = now or now_utc()
    start_day = now.astimezone(doctor_timezone(doctor)).date()
    for _, slots in await availability_range(session, doctor, start_day, days, now=now):
        if slots:
            return slots[0]
    return None
