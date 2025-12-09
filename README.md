# Terraform State Backend Stub

A lightweight FastAPI-based HTTP backend for Terraform state management. This stub implementation stores state in memory and supports all standard Terraform HTTP backend operations including state locking.

## Features

- Full Terraform HTTP backend protocol support
- In-memory state storage (suitable for testing/development)
- State locking and unlocking
- Health check endpoint
- RESTful API with proper status codes

## Supported Endpoints

### State Management
- `GET /` - Retrieve current state (404 if no state exists)
- `POST /` - Create or update state
- `DELETE /` - Delete state

### Locking
- `LOCK /` - Lock the state (returns 423 if already locked)
- `UNLOCK /` - Unlock the state

### Health Check
- `GET /health` - Health check endpoint with state information

## Installation

```bash
# Install dependencies using uv
uv sync

# Or using pip
pip install -r requirements.txt
```

## Running the Server

### Using Python directly
```bash
python main.py
```

### Using uvicorn
```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will start on `http://localhost:8000`

## Using with Terraform

Configure your Terraform backend to use this HTTP backend:

```hcl
terraform {
  backend "http" {
    address = "http://localhost:8000/"
    lock_address = "http://localhost:8000/"
    unlock_address = "http://localhost:8000/"
  }
}
```

Then initialize and use Terraform as normal:

```bash
terraform init
terraform plan
terraform apply
```

## API Examples

### Check health
```bash
curl http://localhost:8000/health
```

### Get state (when it exists)
```bash
curl http://localhost:8000/
```

### Update state
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{"version": 4, "terraform_version": "1.0.0", "serial": 1}'
```

### Lock state
```bash
curl -X LOCK http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{"ID": "my-lock-id", "Operation": "OperationTypeApply", "Info": "my-info", "Who": "user@example.com", "Version": "1.0.0", "Created": "2023-01-01T00:00:00Z", "Path": ""}'
```

### Unlock state
```bash
curl -X UNLOCK http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{"ID": "my-lock-id"}'
```

### Delete state
```bash
curl -X DELETE http://localhost:8000/
```

## Running Tests

```bash
uv run pytest -v
```

## Important Notes

- **In-Memory Storage**: State is stored in memory only. Restarting the server will lose all state data.
- **Development Use**: This is a stub implementation intended for testing and development. Do not use in production.
- **No Authentication**: There is no authentication mechanism. Anyone with network access can modify the state.
- **Single Instance**: This implementation is not designed for horizontal scaling or distributed deployments.

## License

This project is provided as-is for development and testing purposes.
