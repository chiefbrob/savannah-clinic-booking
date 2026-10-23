from __future__ import annotations

from tests.helpers import (
    CLINIC_TZ,
    MON,
    TODAY,
    TUE,
    WED,
    at,
    booking_payload,
    make_doctor,
    make_patient,
    next_weekday,
    parse_iso,
    previous_weekday,
)


async def test_lists_upcoming_appointments_soonest_first(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    later = next_weekday(TODAY, WED)
    sooner = next_weekday(TODAY, TUE)
    other = await make_patient(session, name="Other", email="other@example.com")

    # Book deliberately out of order.
    for moment, who in [
        (at(later, "14:00"), patient),
        (at(sooner, "09:00"), patient),
        (at(sooner, "10:00"), other),
    ]:
        response = await client.post(
            "/appointments", json=booking_payload(doctor.id, who.id, moment)
        )
        assert response.status_code == 201

    response = await client.get(f"/patients/{patient.id}/appointments")

    assert response.status_code == 200
    starts = [parse_iso(item["starts_at"]).astimezone(CLINIC_TZ) for item in response.json()]
    assert starts == [at(sooner, "09:00"), at(later, "14:00")]


async def test_upcoming_excludes_cancelled_and_past_by_default(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    future = next_weekday(TODAY, TUE)

    cancelled = (
        await client.post(
            "/appointments", json=booking_payload(doctor.id, patient.id, at(future, "10:00"))
        )
    ).json()
    await client.patch(f"/appointments/{cancelled['id']}/cancel", json={"reason": "Changed plans"})
    kept = (
        await client.post(
            "/appointments", json=booking_payload(doctor.id, patient.id, at(future, "11:00"))
        )
    ).json()

    upcoming = (await client.get(f"/patients/{patient.id}/appointments")).json()
    assert [item["id"] for item in upcoming] == [kept["id"]]

    everything = (
        await client.get(f"/patients/{patient.id}/appointments", params={"include_past": "true"})
    ).json()
    assert {item["id"] for item in everything} == {cancelled["id"], kept["id"]}


async def test_unknown_patient_is_404(client):
    response = await client.get("/patients/00000000-0000-0000-0000-000000000000/appointments")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "patient_not_found"


async def test_lists_and_reads_doctors_and_patients(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)

    doctors = (await client.get("/doctors")).json()
    patients = (await client.get("/patients")).json()

    assert [item["id"] for item in doctors] == [str(doctor.id)]
    assert [item["id"] for item in patients] == [str(patient.id)]
    assert (await client.get(f"/doctors/{doctor.id}")).json()["name"] == doctor.name


async def test_past_appointments_are_not_counted_as_upcoming(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    monday = previous_weekday(TODAY, MON)

    body = (await client.get(f"/patients/{patient.id}/appointments")).json()
    assert body == []

    # A past booking cannot be created through the API, so insert it directly.
    from app.models import Appointment

    session.add(
        Appointment(
            doctor_id=doctor.id,
            patient_id=patient.id,
            starts_at=at(monday, "10:00"),
            ends_at=at(monday, "10:30"),
            status="booked",
        )
    )
    await session.commit()

    assert (await client.get(f"/patients/{patient.id}/appointments")).json() == []
    assert (
        len(
            (
                await client.get(
                    f"/patients/{patient.id}/appointments", params={"include_past": True}
                )
            ).json()
        )
        == 1
    )
