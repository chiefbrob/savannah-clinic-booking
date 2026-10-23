from __future__ import annotations

from datetime import datetime

from tests.helpers import (
    CLINIC_TZ,
    SUN,
    TODAY,
    TUE,
    at,
    booking_payload,
    make_doctor,
    make_patient,
    next_weekday,
    parse_iso,
)


async def test_availability_summary_counts_free_slots_per_day(client, session):
    doctor = await make_doctor(session)

    response = await client.get(f"/doctors/{doctor.id}/availability/summary", params={"days": 14})

    assert response.status_code == 200
    body = response.json()
    assert len(body["days"]) == 14
    assert body["slot_minutes"] == 30

    by_date = {day["date"]: day["free_slots"] for day in body["days"]}
    sunday = next_weekday(TODAY, SUN).isoformat()
    tuesday = next_weekday(TODAY, TUE).isoformat()
    assert by_date[sunday] == 0  # the doctor does not work Sundays
    assert by_date[tuesday] == 16


async def test_summary_and_day_availability_agree(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)

    await client.post(
        "/appointments", json=booking_payload(doctor.id, patient.id, at(day, "10:00"))
    )

    summary = (
        await client.get(f"/doctors/{doctor.id}/availability/summary", params={"days": 14})
    ).json()
    day_slots = (
        await client.get(f"/doctors/{doctor.id}/availability", params={"date": day.isoformat()})
    ).json()["slots"]

    counts = {entry["date"]: entry["free_slots"] for entry in summary["days"]}
    assert counts[day.isoformat()] == len(day_slots) == 15


async def test_next_available_returns_the_soonest_slot_for_each_doctor(client, session):
    doctor = await make_doctor(session)

    response = await client.get("/doctors/next-available")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["doctor"]["id"] == str(doctor.id)

    # FIXED_NOW is 12:00 local; the doctor works to 16:00, so 13:00 is the first slot
    # that clears the one-hour lead time.
    next_slot = parse_iso(rows[0]["next_slot"]).astimezone(CLINIC_TZ)
    assert next_slot == at(TODAY, "13:00")


async def test_booking_stores_notes_and_returns_a_reference(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)
    payload = booking_payload(doctor.id, patient.id, at(day, "10:00")) | {
        "notes": "  Follow-up on blood pressure  "
    }

    response = await client.post("/appointments", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["notes"] == "Follow-up on blood pressure"
    assert body["reference"].startswith("CLN-")
    assert len(body["reference"]) == 10


async def test_blank_notes_are_stored_as_null(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)
    payload = booking_payload(doctor.id, patient.id, at(day, "10:00")) | {"notes": "   "}

    response = await client.post("/appointments", json=payload)

    assert response.status_code == 201
    assert response.json()["notes"] is None


async def test_next_available_is_null_when_the_window_is_empty(client, session):
    doctor = await make_doctor(session, windows=[(TUE, "08:00", "09:00")])

    # 14 days always contains a Tuesday, so this doctor is never fully booked out;
    # instead check a doctor with no schedule at all.
    from tests.helpers import make_doctor as make

    empty = await make(session, name="Dr Absent", email="absent@clinic.example", windows=[])

    rows = {
        row["doctor"]["id"]: row for row in (await client.get("/doctors/next-available")).json()
    }
    assert rows[str(empty.id)]["next_slot"] is None
    assert rows[str(doctor.id)]["next_slot"] is not None


async def test_summary_is_computed_in_the_clinic_timezone(client, session):
    doctor = await make_doctor(session)

    summary = (await client.get(f"/doctors/{doctor.id}/availability/summary")).json()
    first_day = datetime.fromisoformat(summary["days"][0]["date"])
    assert summary["timezone"] == "Africa/Nairobi"
    assert first_day is not None
