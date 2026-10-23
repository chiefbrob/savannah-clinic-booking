from __future__ import annotations


async def test_registering_a_patient_returns_201_and_normalises_the_email(client):
    response = await client.post(
        "/patients",
        json={
            "name": "  Jane  Wanjiku ",
            "email": "Jane.Wanjiku@Example.COM",
            "phone": "+254712345678",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jane.wanjiku@example.com"
    assert body["name"] == "Jane Wanjiku"
    assert body["id"]


async def test_registering_the_same_email_twice_is_409_and_points_at_the_existing_record(client):
    first = await client.post(
        "/patients", json={"name": "Jane Wanjiku", "email": "jane@example.com"}
    )
    assert first.status_code == 201

    second = await client.post("/patients", json={"name": "Jane W", "email": "JANE@example.com"})

    assert second.status_code == 409
    error = second.json()["error"]
    assert error["code"] == "patient_email_taken"
    assert error["details"]["patient_id"] == first.json()["id"]


async def test_lookup_by_email_finds_the_patient(client):
    created = (
        await client.post("/patients", json={"name": "Jane Wanjiku", "email": "jane@example.com"})
    ).json()

    found = await client.get("/patients/lookup", params={"email": "JANE@example.com"})

    assert found.status_code == 200
    assert found.json()["id"] == created["id"]


async def test_lookup_of_an_unknown_email_is_404(client):
    response = await client.get("/patients/lookup", params={"email": "nobody@example.com"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "patient_not_found"


async def test_a_malformed_email_is_422(client):
    response = await client.post("/patients", json={"name": "Jane", "email": "not-an-email"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_registered_patient_can_then_book(client, session):
    from tests.helpers import TODAY, TUE, at, booking_payload, make_doctor, next_weekday

    doctor = await make_doctor(session)
    patient = (
        await client.post("/patients", json={"name": "New Person", "email": "new@example.com"})
    ).json()
    day = next_weekday(TODAY, TUE)

    response = await client.post(
        "/appointments", json=booking_payload(doctor.id, patient["id"], at(day, "10:00"))
    )

    assert response.status_code == 201
    assert response.json()["patient_id"] == patient["id"]
