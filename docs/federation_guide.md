# Federation Setup & Testing Guide

This guide explains how to connect two independent AetherStore instances (e.g., in different GitHub Codespaces) into a single federated network with unified storage and metadata.

## 1. Networking Setup

### Codespace A (The Bootstrap Hub)
1.  Open the **Ports** tab in VS Code.
2.  Find port **8001** (Node 1).
3.  Right-click the visibility and change it to **Public**.
4.  Copy the **Forwarded Address** (e.g., `https://...-8001.app.github.dev`).

### Codespace B (The Joiner)
1.  Open your `.env` file or `docker-compose.yml`.
2.  Set `BOOTSTRAP_NODE` to the URL you copied from Codespace A.
3.  Set `FEDERATION_SECRET` to the **SAME** value used in Codespace A.
4.  Restart your services: `docker compose down && docker compose up -d`.

## 2. Verification Steps

### Step 1: Connectivity (Gossip)
Check the logs of a node in Codespace B:
```bash
docker compose logs aether-node-1 | grep "DHT"
```
You should see: `DHT bootstrapped to https://... (ID: abc12345)`.

### Step 2: Storage Sync
1.  Upload a file in **Codespace A**.
2.  In **Codespace B**, log in with the **same wallet**.
3.  Refresh the **My Drive** page.
4.  The file should appear automatically (Metadata Sync).
5.  Click **Download**. The shards will be fetched from Codespace A's nodes via the public link.

## 3. High Latency & Stability
AetherStore uses Kademlia's XOR metric to handle latency. If the link between Codespaces is slow, the DHT will favor local nodes first but will always fall back to the remote instance if shards are only available there.

## 4. Troubleshooting
- **Signature Mismatch**: Ensure `FEDERATION_SECRET` is identical in both environments.
- **Connection Refused**: Confirm port 8001 in Codespace A is set to **Public** visibility.
- **Metadata not appearing**: Check `aether-backend` logs for `[Sync]` tags to see if discovery is triggering.
