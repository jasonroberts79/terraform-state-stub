from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    """Test that the health check endpoint returns status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()
    assert response.json()["status"] == "healthy"
