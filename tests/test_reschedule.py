from __future__ import annotations

from tests.helpers import (
    CLINIC_TZ,
    TODAY,
    TUE,
    at,
    booking_payload,
    make_doctor,
    make_patient,
    next_weekday,
    parse_iso,
)


async def test_reschedule_moves_the_appointment_and_frees_the_old_slot(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)
    original = at(day, "10:00")
    target = at(day, "14:00")

    appointment = (
        await client.post("/appointments", json=booking_payload(doctor.id, patient.id, original))
    ).json()

    response = await client.patch(
        f"/appointments/{appointment['id']}/reschedule",
        json={"starts_at": target.isoformat()},
    )

    assert response.status_code == 200
    body = response.json()
    assert parse_iso(body["starts_at"]).astimezone(CLINIC_TZ) == target
    assert body["id"] == appointment["id"]  # same appointment, moved

    slots = {
        parse_iso(slot["starts_at"]).astimezone(CLINIC_TZ)
        for slot in (
            await client.get(f"/doctors/{doctor.id}/availability", params={"date": day.isoformat()})
        ).json()["slots"]
    }
    assert original in slots
    assert target not in slots


async def test_reschedule_onto_a_taken_slot_fails_and_keeps_the_original(client, session):
    doctor = await make_doctor(session)
    first = await make_patient(session, name="First", email="first@example.com")
    second = await make_patient(session, name="Second", email="second@example.com")
    day = next_weekday(TODAY, TUE)
    original = at(day, "10:00")
    taken = at(day, "11:00")

    appointment = (
        await client.post("/appointments", json=booking_payload(doctor.id, first.id, original))
    ).json()
    assert (
        await client.post("/appointments", json=booking_payload(doctor.id, second.id, taken))
    ).status_code == 201

    response = await client.patch(
        f"/appointments/{appointment['id']}/reschedule", json={"starts_at": taken.isoformat()}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "slot_taken"

    after = (await client.get(f"/appointments/{appointment['id']}")).json()
    assert parse_iso(after["starts_at"]).astimezone(CLINIC_TZ) == original
    assert after["status"] == "booked"


async def test_reschedule_of_a_cancelled_appointment_is_409(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)
    appointment = (
        await client.post(
            "/appointments", json=booking_payload(doctor.id, patient.id, at(day, "10:00"))
        )
    ).json()
    await client.patch(f"/appointments/{appointment['id']}/cancel", json={"reason": "Done"})

    response = await client.patch(
        f"/appointments/{appointment['id']}/reschedule",
        json={"starts_at": at(day, "14:00").isoformat()},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "appointment_cancelled"


async def test_reschedule_validates_the_new_slot_like_a_fresh_booking(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)
    appointment = (
        await client.post(
            "/appointments", json=booking_payload(doctor.id, patient.id, at(day, "10:00"))
        )
    ).json()

    outside = await client.patch(
        f"/appointments/{appointment['id']}/reschedule",
        json={"starts_at": at(day, "20:00").isoformat()},
    )
    misaligned = await client.patch(
        f"/appointments/{appointment['id']}/reschedule",
        json={"starts_at": at(day, "11:15").isoformat()},
    )

    assert outside.status_code == 400
    assert outside.json()["error"]["code"] == "outside_working_hours"
    assert misaligned.status_code == 400
    assert misaligned.json()["error"]["code"] == "slot_not_aligned"


async def test_reschedule_to_the_same_slot_is_a_no_op(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)
    moment = at(day, "10:00")
    appointment = (
        await client.post("/appointments", json=booking_payload(doctor.id, patient.id, moment))
    ).json()

    response = await client.patch(
        f"/appointments/{appointment['id']}/reschedule", json={"starts_at": moment.isoformat()}
    )

    assert response.status_code == 200
    assert parse_iso(response.json()["starts_at"]).astimezone(CLINIC_TZ) == moment
