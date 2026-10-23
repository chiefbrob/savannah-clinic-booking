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


async def test_lists_every_scheduled_slot(client, session):
    doctor = await make_doctor(session)
    day = next_weekday(TODAY, TUE)

    response = await client.get(
        f"/doctors/{doctor.id}/availability", params={"date": day.isoformat()}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["slot_minutes"] == 30
    assert body["timezone"] == "Africa/Nairobi"
    assert len(body["slots"]) == 16  # 08:00-16:00 in 30-minute slots

    first = parse_iso(body["slots"][0]["starts_at"]).astimezone(CLINIC_TZ)
    last = parse_iso(body["slots"][-1]["starts_at"]).astimezone(CLINIC_TZ)
    assert first.strftime("%H:%M") == "08:00"
    assert last.strftime("%H:%M") == "15:30"


async def test_booked_slots_disappear_from_availability(client, session):
    doctor = await make_doctor(session)
    patient = await make_patient(session)
    day = next_weekday(TODAY, TUE)

    booked = await client.post(
        "/appointments", json=booking_payload(doctor.id, patient.id, at(day, "10:00"))
    )
    assert booked.status_code == 201

    body = (
        await client.get(f"/doctors/{doctor.id}/availability", params={"date": day.isoformat()})
    ).json()
    starts = {
        parse_iso(slot["starts_at"]).astimezone(CLINIC_TZ).strftime("%H:%M")
        for slot in body["slots"]
    }
    assert len(body["slots"]) == 15
    assert "10:00" not in starts
    assert "10:30" in starts


async def test_hides_slots_inside_the_one_hour_lead_time(client, session):
    # FIXED_NOW is 12:00 in Nairobi, so nothing before 13:00 may be offered today.
    doctor = await make_doctor(session)

    body = (
        await client.get(f"/doctors/{doctor.id}/availability", params={"date": TODAY.isoformat()})
    ).json()

    starts = [parse_iso(slot["starts_at"]).astimezone(CLINIC_TZ) for slot in body["slots"]]
    assert starts, "the doctor works today, so later slots must be offered"
    assert starts[0].strftime("%H:%M") == "13:00"
    assert all(moment > datetime(2026, 11, 2, 12, 0, tzinfo=CLINIC_TZ) for moment in starts)


async def test_returns_no_slots_on_a_day_the_doctor_does_not_work(client, session):
    doctor = await make_doctor(session)
    sunday = next_weekday(TODAY, SUN)

    body = (
        await client.get(f"/doctors/{doctor.id}/availability", params={"date": sunday.isoformat()})
    ).json()

    assert body["slots"] == []


async def test_split_shift_produces_two_windows_in_one_day(client, session):
    doctor = await make_doctor(
        session,
        windows=[(TUE, "08:00", "10:00"), (TUE, "14:00", "16:00")],
    )
    day = next_weekday(TODAY, TUE)

    body = (
        await client.get(f"/doctors/{doctor.id}/availability", params={"date": day.isoformat()})
    ).json()

    starts = [
        parse_iso(slot["starts_at"]).astimezone(CLINIC_TZ).strftime("%H:%M")
        for slot in body["slots"]
    ]
    assert starts == ["08:00", "08:30", "09:00", "09:30", "14:00", "14:30", "15:00", "15:30"]


async def test_unknown_doctor_is_404_with_error_envelope(client):
    response = await client.get(
        "/doctors/00000000-0000-0000-0000-000000000000/availability",
        params={"date": TODAY.isoformat()},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "doctor_not_found"
