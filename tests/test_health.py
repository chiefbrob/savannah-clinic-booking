from __future__ import annotations


async def test_health_reports_database_status(client):
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["timezone"] == "Africa/Nairobi"


async def test_unknown_route_uses_the_error_envelope(client):
    response = await client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_openapi_schema_is_served(client):
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/appointments" in paths
    assert "/doctors/{doctor_id}/availability" in paths
