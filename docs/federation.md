# AetherStore Multi-Server Federation Guide

This guide explains how to link multiple independent Docker-powered servers into a single, unified AetherStore Federated Network.

## Architecture Overview

In a federated setup, each server runs its own local "stack" (DB, Redis, Backend, Nodes), but they share a common **Kademlia Distributed Hash Table (DHT)**. This allows:
- **Server A** to store data on **Server B**.
- Users to discover the entire network's capacity.
- Resilience if one server goes offline.

## Step 1: Configure Server A (Bootstrap Node)

Server A will act as the entry point for other servers.

1.  **Determine Public IP**: `SERVER_A_IP` (e.g., `1.2.3.4`).
2.  **Expose Ports**: Ensure ports `8001-8006` (UDP/TCP) are open in your firewall.
3.  **Update docker-compose.yml**:
    Set the `NODE_ADDRESS` for your nodes to the public IP.
    ```yaml
    node-1:
      environment:
        - NODE_ADDRESS=1.2.3.4
        - NODE_PORT=8001
    ```
4.  **Start Stack**: `docker-compose up -d`.

## Step 2: Configure Server B (Joining Node)

Server B will join Server A's network.

1.  **Start with Server A's Address**: You need `SERVER_A_IP:8001`.
2.  **Update docker-compose.yml**:
    Point the bootstrap environment variable to Server A.
    ```yaml
    node-1:
      environment:
        - NODE_ADDRESS=5.6.7.8  # Server B's public IP
        - BOOTSTRAP_NODE=1.2.3.4:8001
    ```
3.  **Start Stack**: `docker-compose up -d`.

## Step 3: Vercel Frontend Configuration

Since the frontend is hosted on Vercel, you need to point it to one of your backend servers.

1.  Go to **Vercel Project Settings > Environment Variables**.
2.  Set `VITE_API_BASE_URL` to `http://SERVER_A_IP:8000/api/v1`.
3.  Deploy.

## FAQ

### Do I need two Admins?
Each stack has its own Django database and Admin panel. In a federated setup, you usually pick one server as your "Primary" dashboard for your nodes, or maintain both. The *storage layer* is shared, but the *application metadata* (user accounts, buckets) remains local to the specific Django DB.

### How do I sync metadata?
For a true global metadata sync, both servers should point to the same Postgres database (not recommended for simple federation) or use a cross-database sync tool. Federated nodes primarily share **Data Shards**, not user profiles.
