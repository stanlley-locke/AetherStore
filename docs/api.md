# AetherStore API Reference

AetherStore operates two core API groups: the central Django API for users to orchestrate actions, and the decentralized P2P API for Nodes to physically store and recall file shards.

---

## Django API (User Endpoints)
The User API is served from the central Tracker application (e.g. `localhost:8000`). It is authenticated using Decentralized Identifiers (DIDs). 
All endpoints expect an `Authorization` Header formatted precisely as:
`DID-Signature did:example:{username}:fakesig:{timestamp}:{nonce}`

### 1. Upload Object
`POST /api/v1/upload/{bucket_name}/`
Uploads a file to a logical bucket. Asynchronous—returns a Task ID while Celery performs encryption & chunking in the background.

**Request:** Form-Data with the file attached correctly:
`curl -F "file=@/path/to/my/file.txt"`

**Response:** `202 Accepted`
```json
{
  "task_id": "8b7ce2b...",
  "status": "processing",
  "size": 5436474,
  "bucket": "test_bucket",
  "hash": "9e48af1c2..."
}
```

### 2. List Objects
`GET /api/v1/objects/`
Lists all the user's successfully encrypted P2P objects.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Results per page (default: 100)
- `sort`: Ordering style (e.g. `-created_at`)

**Response:** `200 OK`
```json
{
  "objects": [
    {
      "id": "e4f8b...",
      "content_hash": "9e48af1c2...",
      "bucket": "test_bucket",
      "mime_type": "text/plain",
      "size": 5436474,
      "encrypted": true
    }
  ],
  "pagination": { ... }
}
```

### 3. Download Object
`GET /api/v1/download/{object_id}/`
Instructs the server to query the DHT, pull the erasure shards from the P2P cluster, rebuild the file chunks via Reed-Solomon, validate the MAC Auth tags, and decrypt the plaintext directly to your machine stream.

**Response:** binary file blob stream attached with metadata boundaries.

---

## P2P Storage Node (Internal API)
These APIs are exposed by individual peer storage nodes natively on ports like `8001`, `8002`, `8003`. 
They are typically restricted for internal network operations only.

### 1. Health Status
`GET /health`
Validates that the given storage node is alive and accepting chunks.
**Response:** `200 OK`
```json
{"status": "ok", "node_id": "node-1", "is_active": true}
```

### 2. Store Shard
`PUT /shard/{hash}/{chunk_index}/{shard_index}`
The Celery worker triggers this endpoint directly post-encryption to upload mathematical chunks securely without human awareness.

### 3. Retrieve Shard
`GET /shard/{hash}/{chunk_index}/{shard_index}`
Invoked directly during download or repair sequences to recall single 85KB shards into the reconstructor algorithm memory scope.
