# AetherStore Setup Guide

Follow this guide to get the complete AetherStore federated storage environment running on your local machine.

## Recommended: Docker Setup (Quickest)

AetherStore is fully containerized and orchestrated via `docker-compose`. This is the easiest way to launch the entire network including the database, redis, celery, and multiple federated storage nodes.

### 1. Launch the Network
Run the following command from the project root:
```bash
docker-compose up --build
```

This will start:
- **Postgres Database** (Port 5432)
- **Redis Broker** (Port 6379)
- **Django Backend** (Port 8000)
- **Celery Worker & Beat**
- **Nginx Edge Proxy & Frontend** (Port 80)
- **2 Storage Nodes** (Port 8001, 8002)

### 2. Access the Application
- **Frontend/Portal**: [http://localhost](http://localhost)
- **Django Admin**: [http://localhost/admin/](http://localhost/admin/) (Default creds set via scripts/init_network_admin.py)
- **API Health**: [http://localhost/api/v1/p2p/health/](http://localhost/api/v1/p2p/health/)

---

## Alternative: Manual Setup (Development)

Use this method if you want to run the components individually for debugging or more control.

### 1. Backend Initialization
AetherStore uses `uv` for high-performance dependency management.

```bash
# Install uv if you haven't
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies and sync environment
uv sync

# Run migrations
uv run python manage.py migrate

# Initialize Network Admin
uv run python scripts/init_network_admin.py
```

### 2. Infrastructure
Ensure Redis and Postgres are running. If you have Docker, you can start just these:
```bash
docker run -d --name aether-redis -p 6379:6379 redis:7-alpine
docker run -d --name aether-db -e POSTGRES_PASSWORD=secret -e POSTGRES_DB=aether -p 5432:5432 postgres:14-alpine
```

### 3. Start Components
Open separate terminal windows for each:

**A. API Server**
```bash
uv run python manage.py runserver 0.0.0.0:8000
```

**B. Storage Nodes (Minimum 2 for federated network)**
```bash
uv run python apps/p2p/storage_node.py node-1 8001
uv run python apps/p2p/storage_node.py node-2 8002 --bootstrap localhost:8001
```

**C. Celery Worker**
```bash
uv run celery -A aetherstore worker --loglevel=info
```

**D. Frontend (Vite)**
```bash
cd aetherstoreweb
npm install
npm run dev
```

Your local AetherStore cluster is now fully functional! Proceed to the **API Documentation** to start storing objects.
