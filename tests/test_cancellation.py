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


async def test_cancelling_records_the_reason_and_timestamp(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)
    appointment = (
        await client.post(
            "/appointments", json=booking_payload(doctor.id, patient.id, at(day, "10:00"))
        )
    ).json()

    response = await client.patch(
        f"/appointments/{appointment['id']}/cancel", json={"reason": "Patient is travelling"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] == "Patient is travelling"
    assert body["cancelled_at"] is not None


async def test_cancelled_slot_becomes_bookable_again(client, session):
    doctor = await make_doctor(session)
    first = await make_patient(session, name="First", email="first@example.com")
    second = await make_patient(session, name="Second", email="second@example.com")
    day = next_weekday(TODAY, TUE)
    moment = at(day, "10:00")

    appointment = (
        await client.post("/appointments", json=booking_payload(doctor.id, first.id, moment))
    ).json()

    slots_before = (
        await client.get(f"/doctors/{doctor.id}/availability", params={"date": day.isoformat()})
    ).json()["slots"]
    assert moment not in {
        parse_iso(slot["starts_at"]).astimezone(CLINIC_TZ) for slot in slots_before
    }

    await client.patch(f"/appointments/{appointment['id']}/cancel", json={"reason": "Freed up"})

    slots_after = (
        await client.get(f"/doctors/{doctor.id}/availability", params={"date": day.isoformat()})
    ).json()["slots"]
    assert moment in {parse_iso(slot["starts_at"]).astimezone(CLINIC_TZ) for slot in slots_after}

    rebooked = await client.post(
        "/appointments", json=booking_payload(doctor.id, second.id, moment)
    )
    assert rebooked.status_code == 201


async def test_cancelling_twice_is_409(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)
    appointment = (
        await client.post(
            "/appointments", json=booking_payload(doctor.id, patient.id, at(day, "10:00"))
        )
    ).json()

    assert (
        await client.patch(f"/appointments/{appointment['id']}/cancel", json={"reason": "First"})
    ).status_code == 200
    response = await client.patch(
        f"/appointments/{appointment['id']}/cancel", json={"reason": "Second"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "appointment_already_cancelled"


async def test_cancelling_an_unknown_appointment_is_404(client):
    response = await client.patch(
        "/appointments/00000000-0000-0000-0000-000000000000/cancel", json={"reason": "Nope"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "appointment_not_found"


async def test_cancel_requires_a_meaningful_reason(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)
    appointment = (
        await client.post(
            "/appointments", json=booking_payload(doctor.id, patient.id, at(day, "10:00"))
        )
    ).json()

    response = await client.patch(
        f"/appointments/{appointment['id']}/cancel", json={"reason": "  "}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
