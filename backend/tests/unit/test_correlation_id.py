from __future__ import annotations


def test_correlation_id_is_propagated(client) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "request-123"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "request-123"
