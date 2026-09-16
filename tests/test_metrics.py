"""
Smoke-Test für den Atoll-Health-Check-Endpoint /metrics.
"""
from fastapi.testclient import TestClient

from app.main import app


def test_metrics_gibt_200_ok_zurueck():
    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "up 1" in response.text
