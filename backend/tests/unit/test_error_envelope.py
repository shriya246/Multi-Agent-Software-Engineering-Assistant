from __future__ import annotations


def test_error_envelope_for_missing_route(client) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    payload = response.json()
    assert "error" in payload
    assert payload["error"]["code"] == "http_error"
    assert payload["error"]["correlation_id"]
