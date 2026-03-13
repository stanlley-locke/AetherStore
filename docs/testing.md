# AetherStore Full Integration Test Guide

Tests 1 through 14 cover every feature end-to-end using `shakespear.txt`.

---

## ⚡ One-Time Session Setup

Paste ALL of these into your terminal at the start of each test session:

```bash
# Auth token — generates a unique nonce every call
get_auth() { echo "DID-Signature did:example:test_user:fakesig:$(date +%s):test$(date +%s%N)"; }

# Extracts the latest OBJ_ID using Python (no jq required)
# IMPORTANT: CALL this function after each upload completes, not just define it
set_obj_id() {
  OBJ_ID=$(curl -s "http://localhost:8000/api/v1/objects/?page=1&page_size=1&sort=-created_at" \
    -H "Authorization: $(get_auth)" | \
    python -c "import sys,json; print(json.load(sys.stdin)['objects'][0]['id'])")
  echo "OBJ_ID=${OBJ_ID}"
}
```

> ⚠️ **Critical:** After defining `set_obj_id`, you must also **run it** by typing `set_obj_id`.
> Every time you delete an object and re-upload, a new UUID is assigned — call `set_obj_id` again!

### Create Your Node Operator Wallet
Before starting the network, generate your Web3 Non-Custodial wallet. **Save the output!** You will use the `address` to collect ATK mining rewards from your storage nodes.
```bash
# Generate Wallet and store the response
WALLET_JSON=$(curl -s -X POST "http://localhost:8000/api/v1/billing/wallet/generate/" -H "Authorization: $(get_auth)")

# Extract public address, mnemonic, and private key
NODE_WALLET=$(echo $WALLET_JSON | python -c "import sys,json; print(json.load(sys.stdin).get('address', 'ERROR'))")
NODE_MNEMONIC=$(echo $WALLET_JSON | python -c "import sys,json; print(json.load(sys.stdin).get('mnemonic', 'ERROR'))")
NODE_PRIVATE_KEY=$(echo $WALLET_JSON | python -c "import sys,json; print(json.load(sys.stdin).get('private_key', 'ERROR'))")

echo "--- NODE OPERATOR WALLET ---"
echo "Address: ${NODE_WALLET}"
echo "Mnemonic: ${NODE_MNEMONIC}"
echo "Private Key: ${NODE_PRIVATE_KEY}"
echo "----------------------------"

Address: ath1ff47115449d2e3c6ee8ff4dab3e6a0b18c2fa2ad
Mnemonic: now pitch now sad atom surprise empty lecture all mass visit hour
wallet: strong ahead anchor stamp carpet churn mesh gentle owner adjust nothing envelope
Wallet: ramp when green glance nuclear badge casual hat reveal gain stadium biology
Private Key: b3b116a21bea655fde2fc1d03a0eee1a6033bb9885eb067564e2032003b8f879
stanl@stanlley MINGW64 ~/Desktop/vscodeworkspace/pythonplayground/aetherstore (main)
$ python scripts/init_network_admin.py

============================================================
  AetherNode Network Admin Wallet Initializer
============================================================

[!] WARNING: 1 existing admin(s) found:
    - did:aether:ath14c51bc8ea41ed570097e8ccb6aa16a16bfcdcec2

Do you want to create an ADDITIONAL admin? (yes/no): yes

[*] Generating new admin wallet using BIP-39 derivation...

============================================================
  ✅  ADMIN WALLET CREATED SUCCESSFULLY
============================================================

  DID Address    : did:aether:ath1bb0d900a00c89b6e5003aeb3aa4d22c3c4ffd1a1
  Wallet Address : ath1bb0d900a00c89b6e5003aeb3aa4d22c3c4ffd1a1

  ⚠️  RECOVERY PHRASE (store securely, never share!):

  maximum wild sure act hedgehog pumpkin math camp pudding dial hope spy

============================================================

  Use this mnemonic to log in to the AetherNode Admin Portal.
  Navigate to /aethernode/login and paste the phrase above.
============================================================

(aetherstore) 
stanl@stanlley MINGW64 ~/Desktop/vscodeworkspace/pythonplayground/aetherstore (main)
$
```

---

## Test #1: Start Storage Nodes (Required first!)

You must start the central API, Redis broker, Celery worker (`celery -A aetherstore worker -l INFO`) and multiple P2P storage nodes.
Each node must be started in a **separate terminal**.

**Important for Phase 17 Security:**
Storage node operators can now securely pass their web3 public addresses using the `--wallet-address` flag so that rewards bypass internal node wallets and route straight to their main balance. If they don't provide one, an ephemeral wallet is generated on the console once and *never saved to disk*.

```bash
# Terminal 1 — Genesis / bootstrap node (Using your external wallet generated above)
# Replace ${NODE_WALLET} with the actual string if you are copying/pasting terminals!
python apps/p2p/storage_node.py bootstrap-node 8001 --wallet-address ${NODE_WALLET}

# Terminals 2–5 — Peer nodes (Generating secure ephemeral wallets)
python apps/p2p/storage_node.py peer-node 8002 --bootstrap localhost:8001
python apps/p2p/storage_node.py peer-node 8003 --bootstrap localhost:8001
python apps/p2p/storage_node.py peer-node 8004 --bootstrap localhost:8001
python apps/p2p/storage_node.py peer-node 8005 --bootstrap localhost:8001
```

**Expectation:** Each node logs `Storage node ... listening on port 800X` and either announces a newly generated wallet mnemonic (for safekeeping) or configures the external one.

---

## Test #2: Upload `shakespear.txt`

```bash
curl -X POST http://localhost:8000/api/v1/upload/classic_literature/ \
  -H "Authorization: $(get_auth)" \
  -F "file=@shakespear.txt"
```

**Expectation:** `{"status":"processing",...}`. Monitor the Celery terminal and wait for `✓ Stored N shards` (≈1–2 min).

---

## Test #3: Get the Object ID

After Celery finishes, run `set_obj_id` to automatically set the variable:

```bash
# Wait until Celery logs "Upload complete", then:
set_obj_id
# Expected: OBJ_ID=b5e584d1-dc5a-48ca-837b-d270736c04ff (or your current UUID)
```

Verify `OBJ_ID` is a clean UUID:
```bash
echo "OBJ_ID is: ${OBJ_ID}"
# Should look like: OBJ_ID is: b5e584d1-dc5a-48ca-837b-d270736c04ff
```

---

## Test #4: Async Download & Reassembly

```bash
# Step 4a: Queue the background download
curl -X GET "http://localhost:8000/api/v1/download/${OBJ_ID}/" \
  -H "Authorization: $(get_auth)"
```

Extract `task_id` from response using Python:
```bash
TASK_ID=$(curl -s "http://localhost:8000/api/v1/download/${OBJ_ID}/" \
  -H "Authorization: $(get_auth)" | \
  python -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
echo "TASK_ID=${TASK_ID}"
```

```bash
# Step 4b: Poll for completion
curl -X GET "http://localhost:8000/api/v1/download/status/${TASK_ID}/" \
  -H "Authorization: $(get_auth)"

# Step 4c: Save the reassembled file
curl -X GET "http://localhost:8000/api/v1/download/file/${TASK_ID}/" \
  -H "Authorization: $(get_auth)" \
  -o downloaded_shakespear.txt

head -n 25 downloaded_shakespear.txt
```

**Expectation:** First 25 lines are valid Shakespeare text.

---

## Test #5: Media Streaming (HTTP Range Requests)

Stream only the first 100KB — no Celery task needed:

```bash
curl -X GET "http://localhost:8000/api/v1/stream/${OBJ_ID}/" \
  -H "Authorization: $(get_auth)" \
  -H "Range: bytes=0-99999" \
  --output partial_shakespear.txt

head -c 200 partial_shakespear.txt
```

**Expectation:** Instant response with the beginning of the Shakespeare text.

---

## Test #6: Trash & Garbage Collection

```bash
curl -X DELETE "http://localhost:8000/api/v1/object/${OBJ_ID}/" \
  -H "Authorization: $(get_auth)"
```

**Expectation:** `202 Accepted`. Celery runs `garbage_collector` in background, deleting all shards from nodes.

> ⚠️ After deleting, **re-upload** then **call `set_obj_id` again** to get the new UUID before continuing.

---

## Test #7: Multipart Upload (Large Files)

```bash
# Step 1: Initialize session
UPLOAD_RESP=$(curl -s -X POST http://localhost:8000/api/v1/upload/multipart/init/ \
  -H "Authorization: $(get_auth)" \
  -H "Content-Type: application/json" \
  -d '{"bucket_name": "classic_literature", "filename": "shakespear_massive.txt", "mime_type": "text/plain"}')
echo $UPLOAD_RESP

# Extract UPLOAD_ID using Python (no jq needed)
UPLOAD_ID=$(echo $UPLOAD_RESP | \
  python -c "import sys,json; print(json.load(sys.stdin)['upload_id'])")
echo "UPLOAD_ID=${UPLOAD_ID}"
```

```bash
# Step 2: Split and upload parts
split -n 2 shakespear.txt part_

curl -X PUT "http://localhost:8000/api/v1/upload/multipart/${UPLOAD_ID}/part/1/" \
  -H "Authorization: $(get_auth)" \
  --data-binary "@part_aa"

curl -X PUT "http://localhost:8000/api/v1/upload/multipart/${UPLOAD_ID}/part/2/" \
  -H "Authorization: $(get_auth)" \
  --data-binary "@part_ab"

# Step 3: Complete
curl -X POST "http://localhost:8000/api/v1/upload/multipart/${UPLOAD_ID}/complete/" \
  -H "Authorization: $(get_auth)"
```

---

## Test #8: Incentive Mechanism & Billing

```bash
# Check balance
curl -X GET "http://localhost:8000/api/v1/billing/wallet/" \
  -H "Authorization: $(get_auth)"

# Deposit 500 credits
curl -X POST "http://localhost:8000/api/v1/billing/deposit/" \
  -H "Authorization: $(get_auth)" \
  -H "Content-Type: application/json" \
  -d '{"amount": "500.00"}'

# Verify new balance
curl -X GET "http://localhost:8000/api/v1/billing/wallet/" \
  -H "Authorization: $(get_auth)"
```

**Expectation:** Balance increases by 500 after the deposit call.

---

## Test #9: Reputation/Trust System

```bash
# Manually trigger the reputation auditor
python manage.py shell -c "
from workers.storage_auditor import audit_nodes
audit_nodes.apply()
"

# Check node reputation scores
python manage.py shell -c "
from apps.storage.models import StorageNode
for n in StorageNode.objects.all():
    print(n.node_id, 'score:', n.reputation_score, 'active:', n.is_active)
"
```

**Expectation:** Any killed/offline node drops `-10` per audit cycle. At ≤10 it gets deactivated.

---

## Test #10: File Versioning

> **Prerequisite:** `OBJ_ID` must be set to the current shakespear.txt UUID.

```bash
# 1. Add content to make it a new version
echo "# Version 2 annotation" >> shakespear.txt

# 2. Re-upload the SAME filename (versioning keeps the same UUID)
curl -X POST http://localhost:8000/api/v1/upload/classic_literature/ \
  -H "Authorization: $(get_auth)" \
  -F "file=@shakespear.txt"
```

Wait for Celery to finish, then:

```bash
# 3. Refresh OBJ_ID (same UUID expected since filename matches)
set_obj_id

# 4. List all versions
curl -s "http://localhost:8000/api/v1/object/${OBJ_ID}/versions/" \
  -H "Authorization: $(get_auth)"
```

**Expectation:** Array with `v1` and `v2` entries (different `root_hash` values).

```bash
# 5. Stream the historical v1 (should NOT contain "Version 2 annotation")
curl -X GET "http://localhost:8000/api/v1/stream/${OBJ_ID}/?version=1" \
  -H "Authorization: $(get_auth)" \
  --output v1_shakespear.txt

tail -n 3 v1_shakespear.txt
```

---

## Test #11: Human-Readable Naming (IPNS-Style)

> **Prerequisite:** `OBJ_ID` must be set and the object must exist (run `set_obj_id` first!).

```bash
# 1. Register a human-readable name
curl -X POST "http://localhost:8000/api/v1/name/" \
  -H "Authorization: $(get_auth)" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"shakespeare-latest\", \"object_id\": \"${OBJ_ID}\"}"
```

**Expectation:** `{"name":"shakespeare-latest","target_object_id":"...","action":"created"}`

```bash
# 2. Look up the name record
curl -s "http://localhost:8000/api/v1/name/shakespeare-latest/" \
  -H "Authorization: $(get_auth)"

# 3. Resolve the name → streams the file (follows redirect with -L)
curl -s -L "http://localhost:8000/api/v1/resolve/shakespeare-latest/" \
  -H "Authorization: $(get_auth)" \
  -H "Range: bytes=0-199" \
  --output resolved.txt

head -c 200 resolved.txt
```

**Expectation:** Server resolves `shakespeare-latest` → redirects → streams Shakespeare.

```bash
# BONUS: Resolve with versioned time-travel
curl -s -L "http://localhost:8000/api/v1/resolve/shakespeare-latest/?version=1" \
  -H "Authorization: $(get_auth)" \
  --output resolved_v1.txt

tail -n 3 resolved_v1.txt
# Should NOT contain "Version 2 annotation"
```

---

## Test #12: Decentralized Messaging

Messaging uses E2E encryption and charges 0.01 credits per text message.

```bash
# 1. Setup Bob's auth function (same as test_user but for Bob)
get_bob_auth() { echo "DID-Signature did:example:bob:fakesig:$(date +%s):bob$(date +%s%N)"; }

# 2. Create a DM conversation with Alice and Bob
# (Using Bob's DID: did:example:bob)
CONV_RESP=$(curl -s -X POST "http://localhost:8000/api/v1/messaging/conversations/" \
  -H "Authorization: $(get_auth)" \
  -H "Content-Type: application/json" \
  -d '{"participants": ["did:example:bob"], "name": "Secret DM"}')
echo $CONV_RESP

# Extract CONV_ID
CONV_ID=$(echo $CONV_RESP | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "CONV_ID=${CONV_ID}"
```

```bash
# 3. Alice sends an encrypted message
curl -s -X POST "http://localhost:8000/api/v1/messaging/conversations/${CONV_ID}/send/" \
  -H "Authorization: $(get_auth)" \
  -H "Content-Type: application/json" \
  -d '{"body": "Hello Bob! This is an E2E encrypted message.", "type": "text"}'
```

```bash
# 4. Bob checks his inbox
curl -s "http://localhost:8000/api/v1/messaging/inbox/" \
  -H "Authorization: $(get_bob_auth)"
```

```bash
# 5. Bob decrypts a specific message
# (Get the latest message ID from the inbox response first)
MSG_ID=$(curl -s "http://localhost:8000/api/v1/messaging/inbox/" -H "Authorization: $(get_bob_auth)" | \
  python -c "import sys,json; print(json.load(sys.stdin)['conversations'][0]['latest_message']['id'])")
echo "MSG_ID=${MSG_ID}"

curl -s "http://localhost:8000/api/v1/messaging/conversations/${CONV_ID}/messages/${MSG_ID}/decrypt/" \
  -H "Authorization: $(get_bob_auth)"
```

**Expectation:** Bob receives the plaintext message after a successful decryption call. Credits are deducted from Alice's wallet.

---

## Test #13: DHT-First Pure Decentralization (Phase 15)

Verify that messaging works even if data is missing from the central database.

### 1. Decentralized Inbox Polling
Bob can check his messages without using the database-backed inbox:
```bash
curl -s "http://localhost:8000/api/v1/messaging/inbox/dht/" \
  -H "Authorization: $(get_bob_auth)"
```
**Expectation:** Response contains the latest messages fetched directly from storage nodes.

### 2. Database Recovery (Heal)
1. Delete a message from the SQL database to simulate loss:
```bash
python manage.py shell -c "from apps.messaging.models import Message; Message.objects.filter(id='${MSG_ID}').delete()"
```
2. Attempt to decrypt it:
```bash
curl -s "http://localhost:8000/api/v1/messaging/conversations/${CONV_ID}/messages/${MSG_ID}/decrypt/" \
  -H "Authorization: $(get_bob_auth)"
```
**Expectation:** The server responds with the decrypted text by recovering the payload from the DHT nodes automatically!

### 3. Background Persistence Sync
Trigger the worker to restore the database from the DHT:
```bash
python manage.py shell -c "from workers.message_delivery import sync_dht_to_db; print(sync_dht_to_db('did:example:bob'))"
```
**Expectation:** The worker logs success and the message is restored to the Django model.

---

## Test #14: Web3 Cryptography, Blockchain Wallets & Mining

AetherStore incorporates true Web3 non-custodial blockchain functionality using Ed25519 signing. The central server doesn't hold the keys.

### 1. Generate Web3 Wallet (Non-Custodial)
The Private Key and Mnemonic are ONLY returned once. Save your `address`, `private_key` and `mnemonic`.
```bash
curl -s -X POST "http://localhost:8000/api/v1/billing/wallet/generate/" \
  -H "Authorization: $(get_auth)" | jq .
```

### 2. Run Python Cryptographic Transfer Test
Run the automated test script to simulate a client-side Web3 app performing secure remote offline signing:
```bash
python test_crypto_transfer.py
```

Under the hood, this simulates:
1. Re-deriving the Ed25519 keypair.
2. Generating a validation payload `"{recipient}:{amount}:{timestamp}"`
3. Running `signature = private_key.sign(payload)`
4. Passing the Public Key, Address, Amount, Timestamp, and Hex Signature to AetherStore's `LedgerTransaction` verifier endpoint `/api/v1/billing/wallet/transfer/`.

### 3. Trigger Active Mining / Storage Payout Rewards
Nodes earn coins for storing and serving data. Run the payout calculator to map DHT Node stats to external `NodeWallets` and credit their balances using Phase 17 logic.

```bash
python manage.py shell -c "from workers.payout_calculator import calculate_payouts; print(calculate_payouts())"
```

Check your updated wallet balance!
```bash
curl -X GET "http://localhost:8000/api/v1/billing/wallet/" \
  -H "Authorization: $(get_auth)"
```

---

## 🛠️ Advanced Tooling: Batch Decryption

Add these functions to your terminal to decrypt multiple messages at once.

### 1. Decrypt Last 10 (DB Inbox)
```bash
# Decrypt latest message from each of the last 10 active conversations
decrypt_last_10_inbox() {
  local auth_fn=$1
  echo "--- Batch Decrypting Database Inbox (Limit 10) ---"
  curl -s "http://localhost:8000/api/v1/messaging/inbox/?limit=10" -H "$($auth_fn)" | \
  python -c "
import sys, json, subprocess
data = json.load(sys.stdin)
for conv in data['conversations']:
    m = conv['latest_message']
    if m:
        c_id, m_id = conv['conversation_id'], m['id']
        txt = subprocess.check_output(['curl', '-s', f'http://localhost:8000/api/v1/messaging/conversations/{c_id}/messages/{m_id}/decrypt/', '-H', '$($auth_fn)']).decode()
        print(f\"[{conv['conversation_name']}] {json.loads(txt).get('plaintext', 'ERR')}\")
"
}
```

### 2. Decrypt All DHT Messages
```bash
# Fetch and decrypt every message currently waiting in the DHT
decrypt_dht_all() {
  local auth_fn=$1
  echo "--- Batch Decrypting DHT P2P Mailbox ---"
  curl -s "http://localhost:8000/api/v1/messaging/inbox/dht/" -H "$($auth_fn)" | \
  python -c "
import sys, json, subprocess
data = json.load(sys.stdin)
for m in data['messages']:
    c_id, m_id = m['conversation_id'], m['id']
    txt = subprocess.check_output(['curl', '-s', f'http://localhost:8000/api/v1/messaging/conversations/{c_id}/messages/{m_id}/decrypt/', '-H', '$($auth_fn)']).decode()
    res = json.loads(txt)
    print(f\"[DHT Source] {res.get('plaintext', 'ERR')} (ID: {m_id[:8]})\")
"
}
```

### 3. Verify Source Metadata
Check whether a message came from the DB or was recovered from DHT:
```bash
# IMPORTANT: Replace CONV_ID and MSG_ID with the actual UUIDs from your logs!
curl -s "http://localhost:8000/api/v1/messaging/conversations/YOUR_CONV_ID/messages/YOUR_MSG_ID/decrypt/" \
  -H "Authorization: $(get_bob_auth)" | python -m json.tool
# Look for \"source\": \"database\" or \"source\": \"dht_recovered\"
```

---

> [!TIP]
> **Pro Tip:** If `sync_dht_to_db` previously returned 0 messages, try again now. I've updated the worker to perform a network-wide DHT search (`find_value`) instead of just checking the local node storage.

---

## Test #15: Rigorous Wallet Scenarios (Alice & Bob)

In this test, we will explicitly simulate recovering Bob's wallet using his Mnemonic, and then executing a secure Ed25519-signed transaction transferring 5.0 ATK coins from Alice to Bob.

### 1. Identify Bob's Wallet
Bob previously generated his non-custodial wallet (and it was not saved to disk). The details are:
- **Address:** `ath1ff47115449d2e3c6ee8ff4dab3e6a0b18c2fa2ad`
- **Mnemonic:** `now pitch now sad atom surprise empty lecture all mass visit hour` 
- **Private Key:** `b3b116a21bea655fde2fc1d03a0eee1a6033bb9885eb067564e2032003b8f879`

### 2. Verify Bob's Wallet Recovery
We explicitly test our new wallet recovery endpoint. By hitting `/api/v1/billing/wallet/recover/` with Bob's mnemonic, the server explicitly binds his imported Web3 wallet to his DID.
```bash
curl -s -X POST "http://localhost:8000/api/v1/billing/wallet/recover/" \
  -H "Authorization: $(get_bob_auth)" \
  -H "Content-Type: application/json" \
  -d '{
    "mnemonic": "now pitch now sad atom surprise empty lecture all mass visit hour"
  }' | python -m json.tool
```

### 3. Check Alice's Starting Balance
Alice is our primary `test_user` who has been paying for storage and messaging. Let's check her current ATK balance:
```bash
curl -s -X GET "http://localhost:8000/api/v1/billing/wallet/" \
  -H "Authorization: $(get_auth)" | python -m json.tool
```

### 4. Create an Offline Cryptographic Signature for Alice
Transferring ATK on AetherStore requires the sender (Alice) to mathematically sign a payload of `{recipient}:{amount}:{timestamp}`. 

First, let's grab Alice's active private key. Running generation again overrides her node-linked address mapping, but her `test_user` balances persist:
```bash
ALICE_WALLET=$(curl -s -X POST "http://localhost:8000/api/v1/billing/wallet/generate/" -H "Authorization: $(get_auth)")
ALICE_PRIV=$(echo $ALICE_WALLET | python -c "import sys,json; print(json.load(sys.stdin).get('private_key', ''))")
ALICE_PUB=$(echo $ALICE_WALLET | python -c "import sys,json; print(json.load(sys.stdin).get('public_key', ''))")
echo "Alice Public: $ALICE_PUB"
```

Now, generate the cryptographic signature locally simulating a Web3 frontend:
```bash
BOB_ADDRESS="ath1ff47115449d2e3c6ee8ff4dab3e6a0b18c2fa2ad"
AMOUNT="5.0"
TIMESTAMP=$(date +%s)

# Python script to generate ed25519 signature
SIGNATURE=$(python -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
import base64

priv_bytes = bytes.fromhex('$ALICE_PRIV')
private_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
payload = f'$BOB_ADDRESS:$AMOUNT:$TIMESTAMP'.encode('utf-8')
signature = private_key.sign(payload)
print(signature.hex())
")
echo "Signature: $SIGNATURE"
```

### 5. Execute the Decentralized Ledger Transfer
Alice broadcasts her signature and public key to the verification nodes to execute the transaction:
```bash
curl -s -X POST "http://localhost:8000/api/v1/billing/wallet/transfer/" \
  -H "Content-Type: application/json" \
  -d "{
    \"public_key\": \"$ALICE_PUB\",
    \"recipient_address\": \"$BOB_ADDRESS\",
    \"amount\": \"$AMOUNT\",
    \"timestamp\": \"$TIMESTAMP\",
    \"signature\": \"$SIGNATURE\"
  }" | python -m json.tool
```

### 6. Verify Balances Post-Transfer
Check Alice's balance (should be exactly 5.0 less than step 3).
```bash
curl -s -X GET "http://localhost:8000/api/v1/billing/wallet/" \
  -H "Authorization: $(get_auth)" | python -m json.tool
```

Check Bob's balance! Because Bob explicitly recovered his wallet using his mnemonic and DID in Step 2, he can organically check his balances natively over the network:
```bash
curl -s -X GET "http://localhost:8000/api/v1/billing/wallet/" \
  -H "Authorization: $(get_bob_auth)" | python -m json.tool


edge:   harvest height ribbon make spoil quote cycle genius setup ceiling creek safe 
chrome: black flavor young ugly culture domain excite drama famous private unusual smoke
user: try owner keep unknown bleak favorite lucky canyon program ceiling roast giraffe
```
