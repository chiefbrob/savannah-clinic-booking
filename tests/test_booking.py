from __future__ import annotations

from datetime import timedelta

from tests.helpers import (
    MON,
    TODAY,
    TUE,
    at,
    booking_payload,
    make_doctor,
    make_patient,
    next_weekday,
    parse_iso,
    previous_weekday,
)


async def test_books_a_valid_slot(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)

    response = await client.post(
        "/appointments", json=booking_payload(doctor.id, patient.id, at(day, "10:00"))
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "booked"
    assert body["doctor_id"] == str(doctor.id)
    assert body["patient_id"] == str(patient.id)
    assert response.headers["Location"] == f"/appointments/{body['id']}"

    start = parse_iso(body["starts_at"])
    end = parse_iso(body["ends_at"])
    assert end - start == timedelta(minutes=30)


async def test_second_booking_for_the_same_slot_is_409(client, session):
    doctor = await make_doctor(session)
    first = await make_patient(session, name="First", email="first@example.com")
    second = await make_patient(session, name="Second", email="second@example.com")
    day = next_weekday(TODAY, TUE)
    moment = at(day, "10:00")

    assert (
        await client.post("/appointments", json=booking_payload(doctor.id, first.id, moment))
    ).status_code == 201
    response = await client.post(
        "/appointments", json=booking_payload(doctor.id, second.id, moment)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "slot_taken"


async def test_rejects_a_time_outside_working_hours(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)

    response = await client.post(
        "/appointments", json=booking_payload(doctor.id, patient.id, at(day, "16:00"))
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "outside_working_hours"


async def test_rejects_a_time_that_is_not_on_the_slot_grid(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)

    response = await client.post(
        "/appointments", json=booking_payload(doctor.id, patient.id, at(day, "10:15"))
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "slot_not_aligned"


async def test_rejects_a_time_in_the_past(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    past_day = previous_weekday(TODAY, MON)

    response = await client.post(
        "/appointments", json=booking_payload(doctor.id, patient.id, at(past_day, "10:00"))
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "appointment_in_past"


async def test_rejects_a_slot_inside_the_one_hour_lead_time(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)

    # FIXED_NOW is 12:00 local; 12:30 is only 30 minutes away.
    response = await client.post(
        "/appointments", json=booking_payload(doctor.id, patient.id, at(TODAY, "12:30"))
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "booking_too_soon"


async def test_accepts_a_slot_exactly_at_the_lead_time_boundary(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)

    # 13:00 is exactly 60 minutes after FIXED_NOW.
    response = await client.post(
        "/appointments", json=booking_payload(doctor.id, patient.id, at(TODAY, "13:00"))
    )

    assert response.status_code == 201


async def test_unknown_doctor_is_404(client, session):
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)

    response = await client.post(
        "/appointments",
        json=booking_payload("00000000-0000-0000-0000-000000000000", patient.id, at(day, "10:00")),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "doctor_not_found"


async def test_unknown_patient_is_404(client, session):
    doctor = await make_doctor(session)
    day = next_weekday(TODAY, TUE)

    response = await client.post(
        "/appointments",
        json=booking_payload(doctor.id, "00000000-0000-0000-0000-000000000000", at(day, "10:00")),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "patient_not_found"


async def test_a_datetime_without_timezone_is_a_validation_error(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)

    response = await client.post(
        "/appointments",
        json={
            "doctor_id": str(doctor.id),
            "patient_id": str(patient.id),
            "starts_at": f"{day.isoformat()}T10:00:00",  # no offset
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "timezone" in str(body["error"]["details"])
