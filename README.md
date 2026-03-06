# AetherStore Documentation

---

## Table of Contents

1. [Overview](#overview)
2. [Setup Guide](#setup-guide)
3. [API Reference](#api-reference)

---

## Overview

**AetherStore** is a production-grade, decentralized object storage system built in Python. It replaces centralized storage silos with a resilient, peer-to-peer architecture using Erasure Coding and Content-Addressable hashing.

### Key Features

- **Distributed Storage** — Files are sharded and distributed across multiple P2P nodes.
- **Erasure Coding** — Reed-Solomon encoding for data durability (6+3 shards by default).
- **Content-Addressable** — SHA-256 hashing for automatic deduplication.

### Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Client    │───▶│  Django API  │───▶│    Redis    │
│ (curl / UI) │    │ (Port 8000)  │    │   (Cache)   │
└─────────────┘    └──────────────┘    └─────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  PostgreSQL  │
                   │  (Metadata)  │
                   └──────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │  Node 1  │    │  Node 2  │    │  Node 3  │
   │  :8001   │    │  :8002   │    │  :8003   │
   └──────────┘    └──────────┘    └──────────┘
```

---

## Setup Guide

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/aetherstore.git
cd aetherstore
```

### Step 2: Create a Virtual Environment

**Windows (Git Bash)**

```bash
python -m venv .venv
source .venv/Scripts/activate
```

**Linux / macOS**

```bash
python -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**`requirements.txt`**

```
Django>=4.2
djangorestframework>=3.14
django-filter>=23.2
psycopg2-binary>=2.9
redis>=4.5
celery>=5.3
httpx>=0.24
aiohttp>=3.8
aiofiles>=23.1
python-dotenv>=1.0
```

### Step 4: Configure Environment

Create a `.env` file in the project root:

```bash
cat > .env << 'EOF'
# Django Settings
DEBUG=True
SECRET_KEY=django-insecure-change-me-in-production
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (PostgreSQL)
DB_NAME=aether
DB_USER=aether
DB_PASSWORD=secret
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# Erasure Coding
RS_DATA_SHARDS=3
RS_PARITY_SHARDS=2
EOF
```

### Step 5: Start Infrastructure

**Option A: Docker (Recommended)**

```bash
# PostgreSQL
docker run -d \
  --name aether-db \
  -p 5432:5432 \
  -e POSTGRES_DB=aether \
  -e POSTGRES_USER=aether \
  -e POSTGRES_PASSWORD=secret \
  postgres:14-alpine

# Redis
docker run -d \
  --name aether-redis \
  -p 6379:6379 \
  redis:alpine
```

**Option B: Local Installation**

Install PostgreSQL and Redis locally, then update `.env` with the correct connection details.

### Step 6: Database Setup

```bash
python manage.py migrate
python manage.py createsuperuser
```

### Step 7: Start Storage Nodes

Open three separate terminals and run one command in each:

```bash
# Terminal 1 — Node 1
python manage.py run_storage_node --node-id=node-1 --port=8001

# Terminal 2 — Node 2
python manage.py run_storage_node --node-id=node-2 --port=8002

# Terminal 3 — Node 3
python manage.py run_storage_node --node-id=node-3 --port=8003
```

### Step 8: Start Celery Worker

```bash
celery -A aetherstore worker --loglevel=info
```

### Step 9: Start the Django Server

```bash
python manage.py runserver 0.0.0.0:8000
```

### Step 10: Verify Setup

**Health Check**

```bash
curl http://localhost:8000/api/v1/health/
```

Expected response:

```json
{
  "status": "healthy",
  "timestamp": "2026-03-06T08:00:00.000000+00:00",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "storage_nodes": "3 active"
  }
}
```

**Test Upload / Download**

```bash
# Create a test file
echo "Hello AetherStore" > test.txt

# Upload
curl -X POST http://localhost:8000/api/v1/upload/music/ \
  -H "Authorization: DID-Signature did:example:locke:fakesig:$(date +%s):nonce$(date +%s%N)" \
  -F "file=@test.txt"

# Wait for async processing
sleep 10

# Download
curl -X GET http://localhost:8000/api/v1/download/1/ \
  -H "Authorization: DID-Signature did:example:locke:fakesig:$(date +%s):nonce$(date +%s%N)" \
  -o downloaded.txt
```

**Admin Panel**

Access the admin panel at `http://localhost:8000/admin/` and log in with the superuser credentials created in Step 6.

---

### Troubleshooting

**PostgreSQL Connection Error**

```bash
# Check if the container is running
docker ps | grep aether-db

# View logs
docker logs aether-db
```

**Redis Connection Error**

```bash
# Check if Redis is running
docker ps | grep aether-redis

# Test connection
docker exec -it aether-redis redis-cli ping
```

**Celery Not Processing Tasks**

```bash
# Restart the Celery worker
celery -A aetherstore worker --loglevel=debug
```

**Storage Node Not Starting**

```bash
# Check if the port is already in use
netstat -ano | findstr :8001

# Kill the conflicting process if needed
taskkill /PID <PID> /F

# Restart the node
python manage.py run_storage_node --node-id=node-1 --port=8001
```

---

### Production Deployment Checklist

Before deploying to production, ensure the following:

- Set `DEBUG=False` in `.env`.
- Use a strong, randomly generated `SECRET_KEY`.
- Configure proper database credentials and restrict access.
- Use a production WSGI server such as Gunicorn or uWSGI.
- Set up SSL/TLS termination (e.g., via Nginx or a load balancer).
- Configure structured logging and a log aggregation service.
- Set up monitoring and alerting (e.g., Prometheus + Grafana).
- Use a secrets manager instead of plain `.env` files.

---

## API Reference

### Base URL

```
http://localhost:8000/api/v1/
```

### Authentication

All protected endpoints require a `DID-Signature` header in the following format:

```
Authorization: DID-Signature <did>:<signature>:<timestamp>:<nonce>
```

| Component | Description | Example |
|-----------|-------------|---------|
| `did` | Decentralized Identifier | `did:example:locke` |
| `signature` | Cryptographic signature (optional in dev) | `fakesignature` |
| `timestamp` | Unix timestamp in seconds | `1772777000` |
| `nonce` | Unique value to prevent replay attacks | `nonce123456` |

**Generating a timestamp and nonce:**

```bash
TIMESTAMP=$(date +%s)
NONCE="test$(date +%s%N)"
```

---

### Health & Monitoring

#### `GET /health/`

Check system health status. Authentication is **not** required.

```json
{
  "status": "healthy",
  "timestamp": "2026-03-06T08:00:00.000000+00:00",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "storage_nodes": "3 active"
  }
}
```

#### `GET /metrics/`

Returns Prometheus-style metrics. Authentication is **not** required.

#### `GET /stats/`

Returns system and per-user statistics. Authentication is **required**.

```json
{
  "user": {
    "did": "did:example:locke",
    "total_objects": 5,
    "total_size": 1048576,
    "total_size_human": "1.00 MB",
    "buckets": 2
  },
  "system": {
    "total_objects": 100
  }
}
```

---

### File Operations

#### `POST /upload/{bucket_name}/`

Upload a file to a named bucket. Authentication is **required**.

**Path parameter:** `bucket_name` — the name of the destination bucket.

```bash
curl -X POST http://localhost:8000/api/v1/upload/music/ \
  -H "Authorization: DID-Signature did:example:locke:fakesig:1772777000:nonce123" \
  -F "file=@test.txt"
```

**Response `202 Accepted`:**

```json
{
  "task_id": "abc123-def456-...",
  "status": "processing",
  "size": 1024,
  "bucket": "music",
  "mime_type": "text/plain",
  "filename": "test.txt",
  "hash": "sha256hash...",
  "message": "Upload queued for processing"
}
```

**Error responses:**

```json
// 400 Bad Request
{"error": "No file provided", "code": "NO_FILE"}

// 403 Forbidden
{"error": "Storage quota exceeded", "code": "QUOTA_EXCEEDED", "used": 1000000, "quota": 10737418240}

// 500 Internal Server Error
{"error": "Error message", "code": "UPLOAD_ERROR"}
```

---

#### `GET /download/{object_id}/`

Download a file by its object ID. Authentication is **required**.

**Path parameter:** `object_id` — UUID of the object.

**Optional header:** `Range: bytes=0-1023` for partial downloads.

```bash
# Full download
curl -X GET http://localhost:8000/api/v1/download/abc123/ \
  -H "Authorization: DID-Signature did:example:locke:fakesig:1772777000:nonce123" \
  -o downloaded.txt

# Partial download (first 1 KB)
curl -X GET http://localhost:8000/api/v1/download/abc123/ \
  -H "Authorization: DID-Signature did:example:locke:fakesig:1772777000:nonce123" \
  -H "Range: bytes=0-1023" \
  -o partial.txt
```

**Response:** `200 OK` or `206 Partial Content` with binary file content.
Response headers include: `Content-Type`, `Content-Length`, `Content-Disposition`, `Accept-Ranges`.

**Error responses:**

```json
// 403 Forbidden
{"error": "Access denied", "code": "ACCESS_DENIED"}

// 404 Not Found
{"error": "Object not found", "code": "NOT_FOUND"}

// 500 Internal Server Error
{"error": "Insufficient shards: 2/3 needed", "code": "DOWNLOAD_ERROR"}
```

---

### Object Management

#### `GET /objects/`

List objects with filtering and pagination. Authentication is **required**.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | `1` | Page number |
| `page_size` | int | `20` | Items per page |
| `bucket` | string | — | Filter by bucket name |
| `mime_type` | string | — | Filter by MIME type |
| `search` | string | — | Search by hash or MIME type |
| `sort` | string | `-created_at` | Sort field |

```bash
curl -X GET "http://localhost:8000/api/v1/objects/?page=1&page_size=10&bucket=music" \
  -H "Authorization: DID-Signature did:example:locke:fakesig:1772777000:nonce123"
```

**Response:**

```json
{
  "objects": [
    {
      "id": 3,
      "content_hash": "sha256hash...",
      "bucket": "music",
      "mime_type": "text/plain",
      "size": 1024,
      "created_at": "2026-03-06T08:00:00+00:00",
      "updated_at": "2026-03-06T08:00:00+00:00"
    }
  ]
}
```

---

#### `GET /object/{object_id}/`

Retrieve metadata for a single object. Authentication is **required**.

```json
{
  "id": 3,
  "content_hash": "sha256hash...",
  "bucket": 4,
  "bucket_name": "music",
  "mime_type": "text/plain",
  "size": 1024,
  "owner_did": "did:example:locke",
  "shard_map": {
    "node-1": 0
  }
}
```

---

#### `DELETE /object/{object_id}/`

Soft-delete an object. Authentication is **required**.

```json
{
  "status": "deleted",
  "object_id": "abc123"
}
```

---

### Presigned URLs

#### `POST /object/{object_id}/presigned/`

Generate a time-limited presigned download URL. Authentication is **required**.

```bash
curl -X POST http://localhost:8000/api/v1/object/abc123/presigned/ \
  -H "Authorization: DID-Signature did:example:locke:fakesig:1772777000:nonce123" \
  -H "Content-Type: application/json" \
  -d '{"ttl": 3600}'
```

**Response:**

```json
{
  "url": "/api/v1/download/presigned/eyJvYmoiOiIxIiwiZGlkIjoi...",
  "expires_in": 3600,
  "expires_at": "2026-03-06T09:00:00+00:00",
  "object_id": "abc123",
  "size": 1024
}
```

---

#### `GET /download/presigned/{token}/`

Download a file using a presigned URL. Authentication is **not** required.

```bash
curl -X GET http://localhost:8000/api/v1/download/presigned/eyJvYmoiOiIxIiwiZGlkIjoi.../ \
  -o downloaded.txt
```

---

### Bucket Operations

#### `GET /buckets/`

List the authenticated user's buckets. Authentication is **required**.

#### `GET /buckets/{bucket_id}/stats/`

Get statistics for a specific bucket. Authentication is **required**.

```json
{
  "bucket": "music",
  "bucket_id": "abc123",
  "owner_did": "did:example:locke",
  "created_at": "2026-03-06T08:00:00+00:00",
  "statistics": {
    "total_objects": 10,
    "total_size": 10485760,
    "average_size": 1048576,
    "min_size": 1024
  }
}
```

#### `GET /buckets/{bucket_id}/objects/`

List all objects within a specific bucket. Authentication is **required**.

---

### Storage Node Operations (Admin Only)

| Endpoint | Description |
|----------|-------------|
| `GET /nodes/` | List all storage nodes |
| `GET /nodes/active/` | List only active nodes |
| `GET /nodes/health/` | Check health of all nodes |

**`GET /nodes/health/` response:**

```json
{
  "total_nodes": 3,
  "active_nodes": 3,
  "healthy_nodes": 3,
  "nodes": [
    {
      "node_id": "node-1",
      "endpoint": "http://localhost:8001",
      "is_active": true,
      "health": {"status": "healthy"}
    }
  ]
}
```

---

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `NO_FILE` | 400 | No file provided in upload |
| `EMPTY_FILE` | 400 | Empty file not allowed |
| `NO_FILES` | 400 | No files in batch upload |
| `TOO_MANY_FILES` | 400 | Exceeded batch upload limit |
| `QUOTA_EXCEEDED` | 403 | Storage quota exceeded |
| `ACCESS_DENIED` | 403 | User not authorised |
| `NOT_FOUND` | 404 | Object not found |
| `INVALID_TTL` | 400 | Presigned URL TTL is invalid |
| `UPLOAD_ERROR` | 500 | Upload processing failed |
| `DOWNLOAD_ERROR` | 500 | Download processing failed |
| `PRESIGNED_ERROR` | 500 | Presigned URL generation failed |
| `LIST_ERROR` | 500 | Object listing failed |
| `SEARCH_ERROR` | 500 | Search failed |

---

### Rate Limiting

| User Type | Limit |
|-----------|-------|
| Anonymous | 100 requests / hour |
| Authenticated | 1,000 requests / hour |

---

### Best Practices

- **Always use fresh nonces** — each request must carry a unique nonce value.
- **Keep timestamps recent** — the timestamp must be within 5 minutes of server time.
- **Handle async uploads** — upload tasks are processed asynchronously; poll for completion.
- **Use presigned URLs** — share files without exposing user credentials.
- **Implement exponential backoff** — retry failed requests with increasing delay intervals.
- **Cache object metadata** — reduce API call volume for frequently accessed objects.

---

## License

MIT License
