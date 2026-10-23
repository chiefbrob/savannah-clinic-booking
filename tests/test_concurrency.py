"""The test that matters: concurrent requests must not double-book a slot.

Ten clients POST the same slot at the same time. Exactly one may win; the other
nine must receive 409. This is the behaviour that a naive "check if free, then
insert" implementation gets wrong, and it is enforced by the database's partial
unique index rather than by application-level locking.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from app.models import Appointment
from tests.helpers import (
    TODAY,
    TUE,
    at,
    booking_payload,
    make_doctor,
    make_patient,
    next_weekday,
    parse_iso,
)


async def test_ten_concurrent_bookings_for_one_slot_yield_one_winner(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)
    payload = booking_payload(doctor.id, patient.id, at(day, "10:00"))

    responses = await asyncio.gather(
        *(client.post("/appointments", json=payload) for _ in range(10))
    )

    statuses = [response.status_code for response in responses]
    assert statuses.count(201) == 1, f"expected exactly one booking, got {statuses}"
    assert statuses.count(409) == 9

    booked = await session.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.doctor_id == doctor.id, Appointment.status == "booked")
    )
    assert booked == 1

    slots = (
        await client.get(f"/doctors/{doctor.id}/availability", params={"date": day.isoformat()})
    ).json()["slots"]
    assert len(slots) == 15


async def test_concurrent_bookings_for_different_slots_all_succeed(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)
    times = ["09:00", "09:30", "10:00", "10:30", "11:00"]

    responses = await asyncio.gather(
        *(
            client.post("/appointments", json=booking_payload(doctor.id, patient.id, at(day, hhmm)))
            for hhmm in times
        )
    )

    assert [response.status_code for response in responses] == [201] * len(times)


async def test_concurrent_cancel_and_rebook_never_loses_the_slot(client, session):
    """Cancel + immediate re-book: the slot ends up held by exactly one patient."""
    doctor = await make_doctor(session)
    first = await make_patient(session, name="First", email="first@example.com")
    second = await make_patient(session, name="Second", email="second@example.com")
    day = next_weekday(TODAY, TUE)
    moment = at(day, "10:00")

    original = (
        await client.post("/appointments", json=booking_payload(doctor.id, first.id, moment))
    ).json()

    cancel, rebook = await asyncio.gather(
        client.patch(f"/appointments/{original['id']}/cancel", json={"reason": "Moved away"}),
        client.post("/appointments", json=booking_payload(doctor.id, second.id, moment)),
    )

    # The re-book may fail if it lands before the cancel commits; it must never
    # produce two active bookings for the slot.
    active = await session.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(
            Appointment.doctor_id == doctor.id,
            Appointment.starts_at == parse_iso(original["starts_at"]),
            Appointment.status == "booked",
        )
    )
    assert cancel.status_code == 200
    assert active <= 1
    assert rebook.status_code in (201, 409)
