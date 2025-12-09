from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from typing import Optional
import json
from datetime import datetime, UTC

app = FastAPI(title="Terraform State Backend Stub")

# In-memory state storage
state_store: Optional[dict] = None
lock_info: Optional[dict] = None


@app.get("/")
async def get_state():
    """
    Retrieve the current Terraform state.
    Returns 404 if no state exists.
    """
    if state_store is None:
        raise HTTPException(status_code=404, detail="State not found")

    return JSONResponse(content=state_store)


@app.post("/")
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

    return Response(status_code=200)


@app.delete("/")
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
    return Response(status_code=200)


@app.api_route("/", methods=["LOCK"])
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
    return Response(status_code=200)


@app.api_route("/", methods=["UNLOCK"])
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
