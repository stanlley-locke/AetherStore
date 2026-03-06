# Testing Guide (shakespear.txt)

This document provides a complete integration testing workflow for uploading, finding, and downloading the `shakespear.txt` large file dynamically across your local environment.

## Context
When running on `Windows` with Git Bash or MinGW64, we need to generate unique cryptographic validation `Nonces` for **every** HTTP request. AetherStore rejects reused tokens as implicit `Replay Attacks`!

### Define The Bash Header Helper:
Open the root of the project structure in your terminal and declare this one-time ephemeral function:
```bash
get_auth() { echo "DID-Signature did:example:test_user:fakesig:$(date +%s):test$(date +%s%N)"; }
```

---

## Test #1: Upload

Deploy the `shakespear.txt` demo file onto the P2P swarm:
```bash
curl -X POST http://localhost:8000/api/v1/upload/classic_literature/ \
  -H "Authorization: $(get_auth)" \
  -F "file=@shakespear.txt"
```
**Expectation:** The server responds synchronously stating `"status":"processing"`. 
Behind the scenes, your Celery worker is currently slicing the file into ~28 uniquely secured pieces and feeding them to Nodes 1 through 5. Give it about ~2 minutes for local emulation algorithms to complete mathematically.

---

## Test #2: Search & Retrieval

Fetch your database objects once the Celery processing task logs `Upload complete`:

```bash
curl -s -X GET "http://localhost:8000/api/v1/objects/?page=1&page_size=3&sort=-created_at" \
  -H "Authorization: $(get_auth)"
```

**Expectation:** An array of JSON. Locate the `"id"` property representing your `shakespear.txt` object (e.g. `fcbb884c-eeee-4695...`).

---

## Test #3: Download Reassembly

Insert your `id` string block from step #2 into the placeholder below to pull your text file out:

```bash
# Set your target UUID here
OBJ_ID="fcbb884c-eeee-4695-9935-216b91aa0e88"

curl -X GET "http://localhost:8000/api/v1/download/${OBJ_ID}/" \
  -H "Authorization: $(get_auth)" \
  -o downloaded_shakespear.txt
```

### Final Validation
Read the downloaded reassembly output to prove complete cryptographical integrity:
```bash
head -n 25 downloaded_shakespear.txt
```
**Expectation:** You are presented with the perfectly legible starting text of Shakespeare: *First Citizen: Before we proceed any further, hear me speak...*
