from fastapi.testclient import TestClient
import main
from main import app, STATE_FILE, LOCK_FILE
import json
import pytest

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up state and lock files before and after each test."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()

    # Explicitly reset global variables
    main.state_store = None
    main.lock_info = None

    yield

    # Cleanup after test
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()

    # Reset globals again
    main.state_store = None
    main.lock_info = None


def test_health_check():
    """Test that the health check endpoint returns status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()
    assert response.json()["status"] == "healthy"


class TestStateOperations:
    """Test state GET, POST, DELETE operations."""

    def test_get_state_when_empty(self):
        """Test GET returns 404 when no state exists."""
        response = client.get("/tfstate")
        assert response.status_code == 404
        assert "State not found" in response.json()["detail"]

    def test_post_state(self):
        """Test POST creates state."""
        state_data = {
            "version": 4,
            "terraform_version": "1.0.0",
            "resources": []
        }
        response = client.post("/tfstate", json=state_data)
        assert response.status_code == 200

    def test_get_state_after_post(self):
        """Test GET returns state after POST."""
        state_data = {
            "version": 4,
            "terraform_version": "1.0.0",
            "resources": [{"type": "test", "name": "example"}]
        }
        client.post("/tfstate", json=state_data)

        response = client.get("/tfstate")
        assert response.status_code == 200
        assert response.json() == state_data

    def test_update_existing_state(self):
        """Test POST updates existing state."""
        initial_state = {"version": 4, "resources": []}
        client.post("/tfstate", json=initial_state)

        updated_state = {"version": 4, "resources": [{"type": "test"}]}
        response = client.post("/tfstate", json=updated_state)
        assert response.status_code == 200

        get_response = client.get("/tfstate")
        assert get_response.json() == updated_state

    def test_delete_state(self):
        """Test DELETE removes state."""
        state_data = {"version": 4, "resources": []}
        client.post("/tfstate", json=state_data)

        response = client.delete("/tfstate")
        assert response.status_code == 200

        get_response = client.get("/tfstate")
        assert get_response.status_code == 404

    def test_post_invalid_json(self):
        """Test POST with invalid JSON returns 400."""
        response = client.post(
            "/tfstate",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400


class TestLockingOperations:
    """Test LOCK and UNLOCK operations."""

    def test_lock_state(self):
        """Test locking state."""
        lock_data = {
            "ID": "lock-123",
            "Operation": "OperationTypeApply",
            "Info": "test lock",
            "Who": "user@example.com",
            "Version": "1.0.0",
            "Created": "2025-01-01T00:00:00Z",
            "Path": ""
        }
        response = client.request("LOCK", "/lock", json=lock_data)
        assert response.status_code == 200

    def test_unlock_state(self):
        """Test unlocking state."""
        lock_data = {
            "ID": "lock-456",
            "Operation": "OperationTypeApply",
            "Info": "test lock"
        }
        client.request("LOCK", "/lock", json=lock_data)

        response = client.request("UNLOCK", "/lock", json=lock_data)
        assert response.status_code == 200

    def test_lock_already_locked_with_same_id(self):
        """Test locking when already locked with same ID succeeds."""
        lock_data = {"ID": "lock-789", "Operation": "test"}
        client.request("LOCK", "/lock", json=lock_data)

        response = client.request("LOCK", "/lock", json=lock_data)
        assert response.status_code == 200

    def test_lock_already_locked_with_different_id(self):
        """Test locking when already locked with different ID returns 423."""
        lock_data_1 = {"ID": "lock-111", "Operation": "test"}
        client.request("LOCK", "/lock", json=lock_data_1)

        lock_data_2 = {"ID": "lock-222", "Operation": "test"}
        response = client.request("LOCK", "/lock", json=lock_data_2)
        assert response.status_code == 423
        assert response.json()["ID"] == "lock-111"

    def test_unlock_with_wrong_id(self):
        """Test unlocking with wrong ID returns 409."""
        lock_data = {"ID": "lock-aaa", "Operation": "test"}
        client.request("LOCK", "/lock", json=lock_data)

        wrong_lock_data = {"ID": "lock-bbb", "Operation": "test"}
        response = client.request("UNLOCK", "/lock", json=wrong_lock_data)
        assert response.status_code == 409

    def test_unlock_when_not_locked(self):
        """Test unlocking when not locked succeeds."""
        unlock_data = {"ID": "lock-xyz", "Operation": "test"}
        response = client.request("UNLOCK", "/lock", json=unlock_data)
        assert response.status_code == 200


class TestStateAndLockInteraction:
    """Test interaction between state operations and locking."""

    def test_post_state_when_locked_with_wrong_id(self):
        """Test POST state fails when locked with wrong ID."""
        lock_data = {"ID": "lock-correct", "Operation": "test"}
        client.request("LOCK", "/lock", json=lock_data)

        state_data = {"version": 4, "resources": []}
        response = client.post(
            "/tfstate",
            json=state_data,
            headers={"Lock-ID": "lock-wrong"}
        )
        assert response.status_code == 409
        assert "State is locked" in response.json()["detail"]

    def test_post_state_when_locked_with_correct_id(self):
        """Test POST state succeeds when locked with correct ID."""
        lock_data = {"ID": "lock-correct", "Operation": "test"}
        client.request("LOCK", "/lock", json=lock_data)

        state_data = {"version": 4, "resources": []}
        response = client.post(
            "/tfstate",
            json=state_data,
            headers={"Lock-ID": "lock-correct"}
        )
        assert response.status_code == 200

    def test_post_state_when_locked_without_lock_id_header(self):
        """Test POST state fails when locked but no Lock-ID header."""
        lock_data = {"ID": "lock-123", "Operation": "test"}
        client.request("LOCK", "/lock", json=lock_data)

        state_data = {"version": 4, "resources": []}
        response = client.post("/tfstate", json=state_data)
        assert response.status_code == 409

    def test_delete_state_when_locked_with_wrong_id(self):
        """Test DELETE state fails when locked with wrong ID."""
        state_data = {"version": 4, "resources": []}
        client.post("/tfstate", json=state_data)

        lock_data = {"ID": "lock-delete", "Operation": "test"}
        client.request("LOCK", "/lock", json=lock_data)

        response = client.delete(
            "/tfstate",
            headers={"Lock-ID": "wrong-id"}
        )
        assert response.status_code == 409

    def test_delete_state_when_locked_with_correct_id(self):
        """Test DELETE state succeeds when locked with correct ID."""
        state_data = {"version": 4, "resources": []}
        client.post("/tfstate", json=state_data)

        lock_data = {"ID": "lock-delete-ok", "Operation": "test"}
        client.request("LOCK", "/lock", json=lock_data)

        response = client.delete(
            "/tfstate",
            headers={"Lock-ID": "lock-delete-ok"}
        )
        assert response.status_code == 200


class TestPersistence:
    """Test that state and locks persist to files."""

    def test_state_persists_to_file(self):
        """Test state is saved to file."""
        state_data = {"version": 4, "resources": [{"test": "data"}]}
        client.post("/tfstate", json=state_data)

        assert STATE_FILE.exists()
        with open(STATE_FILE, 'r') as f:
            saved_state = json.load(f)
        assert saved_state == state_data

    def test_lock_persists_to_file(self):
        """Test lock info is saved to file."""
        lock_data = {"ID": "lock-persist", "Operation": "test"}
        client.request("LOCK", "/lock", json=lock_data)

        assert LOCK_FILE.exists()
        with open(LOCK_FILE, 'r') as f:
            saved_lock = json.load(f)
        assert saved_lock == lock_data

    def test_state_file_deleted_when_state_deleted(self):
        """Test state file is removed when state is deleted."""
        state_data = {"version": 4, "resources": []}
        client.post("/tfstate", json=state_data)
        assert STATE_FILE.exists()

        client.delete("/tfstate")
        assert not STATE_FILE.exists()

    def test_lock_file_deleted_when_unlocked(self):
        """Test lock file is removed when unlocked."""
        lock_data = {"ID": "lock-temp", "Operation": "test"}
        client.request("LOCK", "/lock", json=lock_data)
        assert LOCK_FILE.exists()

        client.request("UNLOCK", "/lock", json=lock_data)
        assert not LOCK_FILE.exists()

    def test_state_loads_on_startup(self):
        """Test state is loaded from file on startup."""
        # Manually create state file
        state_data = {"version": 4, "resources": [{"restored": True}]}
        with open(STATE_FILE, 'w') as f:
            json.dump(state_data, f)

        # Reload state
        main.load_state()

        # Verify state is available
        response = client.get("/tfstate")
        assert response.status_code == 200
        assert response.json() == state_data

    def test_lock_loads_on_startup(self):
        """Test lock info is loaded from file on startup."""
        # Manually create lock file
        lock_data = {"ID": "lock-restored", "Operation": "test"}
        with open(LOCK_FILE, 'w') as f:
            json.dump(lock_data, f)

        # Reload lock
        main.load_lock()

        # Verify lock is active by trying to lock with different ID
        different_lock = {"ID": "lock-different", "Operation": "test"}
        response = client.request("LOCK", "/lock", json=different_lock)
        assert response.status_code == 423
