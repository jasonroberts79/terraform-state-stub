from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from typing import Optional
import json
from datetime import datetime, UTC
from pathlib import Path

app = FastAPI(title="Terraform State Backend Stub")

# File paths for persistent storage
STATE_FILE = Path("terraform_state.json")
LOCK_FILE = Path("terraform_lock.json")

# In-memory state storage
state_store: Optional[dict] = None
lock_info: Optional[dict] = None


def load_state():
    """Load state from file if it exists."""
    global state_store
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                state_store = json.load(f)
        except (json.JSONDecodeError, IOError):
            state_store = None


def save_state():
    """Save state to file."""
    if state_store is None:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
    else:
        with open(STATE_FILE, 'w') as f:
            json.dump(state_store, f, indent=2)


def load_lock():
    """Load lock info from file if it exists."""
    global lock_info
    if LOCK_FILE.exists():
        try:
            with open(LOCK_FILE, 'r') as f:
                lock_info = json.load(f)
        except (json.JSONDecodeError, IOError):
            lock_info = None


def save_lock():
    """Save lock info to file."""
    if lock_info is None:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    else:
        with open(LOCK_FILE, 'w') as f:
            json.dump(lock_info, f, indent=2)


# Load existing state and lock info on startup
load_state()
load_lock()


@app.get("/tfstate")
async def get_state():
    """
    Retrieve the current Terraform state.
    Returns 404 if no state exists.
    """
    if state_store is None:
        raise HTTPException(status_code=404, detail="State not found")

    return JSONResponse(content=state_store)


@app.post("/tfstate")
async def update_state(request: Request):
    """
    Update or create the Terraform state.
    Terraform sends the Lock-ID header if the state is locked.
    """
    global state_store

    # Check for lock
    lock_id = request.headers.get("Lock-ID")
    if lock_info is not None:
        if lock_id != lock_info.get("ID"):
            raise HTTPException(
                status_code=409,
                detail=f"State is locked: {json.dumps(lock_info)}"
            )

    # Read and store the new state
    body = await request.body()
    try:
        state_store = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    save_state()
    return Response(status_code=200)


@app.delete("/tfstate")
async def delete_state(request: Request):
    """
    Delete the Terraform state.
    Terraform sends the Lock-ID header if the state is locked.
    """
    global state_store

    # Check for lock
    lock_id = request.headers.get("Lock-ID")
    if lock_info is not None:
        if lock_id != lock_info.get("ID"):
            raise HTTPException(
                status_code=409,
                detail=f"State is locked: {json.dumps(lock_info)}"
            )

    state_store = None
    save_state()
    return Response(status_code=200)


@app.api_route("/lock", methods=["LOCK"])
async def lock_state(request: Request):
    """
    Lock the Terraform state.
    Terraform sends lock info in the request body.
    """
    global lock_info

    body = await request.body()
    try:
        new_lock_info = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Check if already locked
    if lock_info is not None:
        if lock_info.get("ID") != new_lock_info.get("ID"):
            return JSONResponse(
                status_code=423,
                content=lock_info
            )

    lock_info = new_lock_info
    save_lock()
    return Response(status_code=200)


@app.api_route("/lock", methods=["UNLOCK"])
async def unlock_state(request: Request):
    """
    Unlock the Terraform state.
    Terraform sends lock info in the request body.
    """
    global lock_info

    body = await request.body()
    try:
        unlock_info = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Verify the lock ID matches
    if lock_info is not None:
        if lock_info.get("ID") != unlock_info.get("ID"):
            return JSONResponse(
                status_code=409,
                content={"error": "Lock ID mismatch"}
            )

    lock_info = None
    save_lock()
    return Response(status_code=200)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "has_state": state_store is not None,
        "is_locked": lock_info is not None,
        "timestamp": datetime.now(UTC).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
