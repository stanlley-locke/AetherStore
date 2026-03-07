# 🗨️ AetherStore Messaging: All-Round Testing Suite

This guide provides a comprehensive set of commands to test every feature of the AetherStore decentralized messaging layer, from E2E encryption to DHT-first inbox recovery.

---

## 1. Setup Authentication Helpers

Run these in your terminal to easily switch between **Alice** (primary test user) and **Bob**.

```bash
# Auth helper for Alice (test_user)
get_alice_auth() { echo "DID-Signature did:example:alice:fakesig:$(date +%s):alice$(date +%s%N)"; }

# Auth helper for Bob
get_bob_auth() { echo "DID-Signature did:example:bob:fakesig:$(date +%s):bob$(date +%s%N)"; }

# Shortcut for primary user
get_auth() { get_alice_auth; }
```

---

## 2. Conversation Management

### Create a DM with Bob
```bash
CONV_RESP=$(curl -s -X POST "http://localhost:8000/api/v1/messaging/conversations/" \
  -H "Authorization: $(get_alice_auth)" \
  -H "Content-Type: application/json" \
  -d '{"participants": ["did:example:bob"], "name": "Secret DM"}')
echo $CONV_RESP

# Save CONV_ID
CONV_ID=$(echo $CONV_RESP | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

### Create a Group Chat
```bash
curl -s -X POST "http://localhost:8000/api/v1/messaging/conversations/" \
  -H "Authorization: $(get_alice_auth)" \
  -H "Content-Type: application/json" \
  -d '{"participants": ["did:example:bob", "did:example:charlie"], "name": "Hackers Collective"}'
```

---

## 3. Sending & Receiving (E2E Encrypted)

### Alice sends a message to Bob
```bash
SENT_RESP=$(curl -s -X POST "http://localhost:8000/api/v1/messaging/conversations/${CONV_ID}/send/" \
  -H "Authorization: $(get_alice_auth)" \
  -H "Content-Type: application/json" \
  -d '{"body": "Hello Bob! This is 100% decentralized.", "type": "text"}')
echo $SENT_RESP

# Save MSG_ID
MSG_ID=$(echo $SENT_RESP | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

### Bob checks his Inboxes
| Inbox Type | Command | Purpose |
| :--- | :--- | :--- |
| **Standard (DB)** | `curl -s "http://localhost:8000/api/v1/messaging/inbox/" -H "Authorization: $(get_bob_auth)"` | Check indexed messages in local storage. |
| **Decentralized (DHT)** | `curl -s "http://localhost:8000/api/v1/messaging/inbox/dht/" -H "Authorization: $(get_bob_auth)"` | Direct P2P query (Works if DB is offline). |

---

## 4. Advanced Decryption & Source Tracking

### Standard Decrypt
```bash
curl -s "http://localhost:8000/api/v1/messaging/conversations/${CONV_ID}/messages/${MSG_ID}/decrypt/" \
  -H "Authorization: $(get_bob_auth)" | python -m json.tool
```
*Look for `"source": "database"` in the response.*

### DHT Recovery (Delete from DB, then Decrypt)
```bash
# 1. Manually delete from SQL
python manage.py shell -c "from apps.messaging.models import Message; Message.objects.filter(id='${MSG_ID}').delete()"

# 2. Decrypt again
curl -s "http://localhost:8000/api/v1/messaging/conversations/${CONV_ID}/messages/${MSG_ID}/decrypt/" \
  -H "Authorization: $(get_bob_auth)" | python -m json.tool
```
*Look for `"source": "dht_recovered"`!*

---

## 5. Batch Decryption Functions

Paste these into your terminal for rapid reading:

```bash
# Decrypt last 10 conversations
decrypt_inbox_10() {
  local auth_fn=$1
  curl -s "http://localhost:8000/api/v1/messaging/inbox/?limit=10" -H "$($auth_fn)" | \
  python -c "
import sys, json, subprocess
data = json.load(sys.stdin)
for conv in data['conversations']:
    m = conv['latest_message']
    if m:
        c_id, m_id = conv['conversation_id'], m['id']
        txt = subprocess.check_output(['curl', '-s', f'http://localhost:8000/api/v1/messaging/conversations/{c_id}/messages/{m_id}/decrypt/', '-H', '$($auth_fn)']).decode()
        print(f\"[{conv.get('conversation_name', 'DM')}] {json.loads(txt).get('plaintext', 'ERR')}\")
"
}

# Decrypt ALL messages waiting in DHT
decrypt_dht_all() {
  local auth_fn=$1
  curl -s "http://localhost:8000/api/v1/messaging/inbox/dht/" -H "$($auth_fn)" | \
  python -c "
import sys, json, subprocess
data = json.load(sys.stdin)
for m in data['messages']:
    c_id, m_id = m['conversation_id'], m['id']
    txt = subprocess.check_output(['curl', '-s', f'http://localhost:8000/api/v1/messaging/conversations/{c_id}/messages/{m_id}/decrypt/', '-H', '$($auth_fn)']).decode()
    res = json.loads(txt)
    print(f\"[DHT SOURCE] {res.get('plaintext', 'ERR')} (ID: {m_id[:8]})\")
"
}
```

Usage: `decrypt_inbox_10 get_bob_auth`

---

## 6. Manual Synchronization (Network Bootstrapping)

If `sync_dht_to_db` returns 0 messages, it's because the shell process hasn't connected to the peer network. Use this command to bootstrap:

```bash
python manage.py shell -c "
from workers.message_delivery import sync_dht_to_db
from apps.core.dht import dht_service
# Manually bootstrap to the running node (usually port 8001 or 8002)
dht = dht_service.get_node()
dht.add_peer_direct('127.0.0.1', 8001) 
print(sync_dht_to_db('did:example:bob'))
"
```

---

## 7. Search & Discovery

### Search for specific keywords
```bash
curl -s "http://localhost:8000/api/v1/messaging/search/?q=decentralized" \
  -H "Authorization: $(get_alice_auth)" | python -m json.tool
```

---

## 8. Offline Mode Verification (Zero-Trust Resilience)

Test the system's ability to operate even when the central Django server is dead.

1.  **Kill the Django Server**: Press `Ctrl+C` in your `runserver` terminal.
2.  **Keep P2P Nodes Running**: Ensure your storage nodes are still active.
3.  **Poll DHT Inbox**:
    ```bash
    # This will FAIL if you hit the Django API, but in a real client, 
    # you would hit the P2P nodes directly.
    # To simulate this locally, keep the Django server ALIVE but 
    # test the /inbox/dht/ endpoint which mimics the P2P logic.
    ```
4.  **Simulate Recovery**:
    *   Restart the Django server.
    *   Manually delete a message from the DB.
    *   The `/decrypt/` endpoint will still work by fetching from the P2P network!

---

> [!IMPORTANT]
> **Variable Subsitution**: Always ensure you substitute `CONV_ID` and `MSG_ID` with the actual UUIDs returned by the API during your test session.
