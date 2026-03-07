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

### 3. Initiate Download
`GET /api/v1/download/{object_id}/`
Instructs the server to asynchronously query the DHT, pull the erasure shards from the P2P cluster, rebuild the file chunks via Reed-Solomon, validate the MAC Auth tags, and decrypt the plaintext.

**Response:** `202 Accepted`
```json
{
  "task_id": "8b7ce2b...",
  "status": "processing",
  "file_size": 5436474,
  "filename": "my_file.txt",
  "message": "Download queued for background reassembly and decryption"
}
```

### 4. Check Download Status
`GET /api/v1/download/status/{task_id}/`
Poll this endpoint to monitor the progress of your background decryption task.

**Response:** `200 OK`
```json
{
  "task_id": "8b7ce2b...",
  "status": "success",
  "output_path": "data/downloads/8b7ce2b....bin",
  "size": 5436474
}
```

### 5. Retrieve Downloaded File
`GET /api/v1/download/file/{task_id}/`
Once the status is `success`, hit this endpoint to retrieve the fully decrypted, reassembled binary payload streamed directly to your machine.

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

---

## Messaging API (Decentralized Communication)
The Messaging layer provides E2E encrypted, P2P-routed communication.

### 1. Create/List Conversations
`POST /api/v1/messaging/conversations/` - Create a DM or Group.
`GET /api/v1/messaging/conversations/` - List user's active conversations.

**Request (Create):**
```json
{
  "participants": ["did:example:bob"],
  "name": "Secret DM",
  "is_group": false
}
```

### 2. Send Encrypted Message
`POST /api/v1/messaging/conversations/{conv_id}/send/`
Sends an AES-256-GCM encrypted message. The body is automatically stored in both the database and the DHT (Phase 15).

**Request:**
```json
{
  "body": "Ciphertext or Plaintext snippet",
  "type": "text",
  "attachment_id": "optional-uuid"
}
```

### 3. Standard Inbox
`GET /api/v1/messaging/inbox/`
Returns a summary of all conversations and the latest message in each, backed by the central SQL database.

### 4. DHT-First Inbox (Pure P2P)
`GET /api/v1/messaging/inbox/dht/`
Queries the P2P storage nodes directly for the latest message envelopes. Works even if the database is offline.

### 5. Decrypt Message (with Recovery)
`GET /api/v1/messaging/conversations/{conv_id}/messages/{msg_id}/decrypt/`
Returns the plaintext of a message. **Phase 15 Enhancement:** If the message is missing from the DB, it automatically recovers the payload from the DHT storage nodes.

### 6. Decentralized Search
`GET /api/v1/messaging/search/?q={query}`
Searches through message metadata and plaintext snippets indexed across the network.

---

## Billing & Incentive API

### 1. Wallet Balance
`GET /api/v1/billing/wallet/`
Returns the current balance (ATK) and the 10 most recent transactions.

### 2. Deposit Funds
`POST /api/v1/billing/deposit/`
Simulates a credit deposit. 
`{"amount": "500.00"}`

---

## Naming & Discovery (IPNS-Style)

### 1. Register Name
`POST /api/v1/name/`
Maps a human-readable string to a P2P Object ID.
`{"name": "my-file", "object_id": "uuid"}`

### 2. Resolve Name
`GET /api/v1/resolve/{name}/`
Redirects to the latest version of the object tracked by the name record.
