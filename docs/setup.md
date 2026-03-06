# AetherStore Local Setup Guide

Follow this guide to get the complete AetherStore decentralized storage environment running on your local machine.

## Prerequisites
- **Python 3.10+**
- **Docker** (for Redis)
- **Git**

## 1. Project Initialization

Clone the repository and install dependencies:
```bash
# Clone the project (if not already done)
git clone https://github.com/yourusername/aetherstore.git
cd aetherstore

# Set up your virtual environment
python -m venv .venv

# Activate it
# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Infrastructure (Redis)

AetherStore relies on Celery for executing expensive cryptography tasks in the background, which requires Redis as a message broker:

```bash
docker run -d --name aether-redis -p 6379:6379 redis:7-alpine
```

## 3. Django Server

The central Django API handles authentication, orchestrates the background encryption tasks, and maintains object metadata:

```bash
# Initialize the database
python manage.py makemigrations
python manage.py migrate

# Start the Django server
python manage.py runserver 0.0.0.0:8000
```

## 4. Peer-to-Peer Storage Nodes

AetherStore uses an Erasure Coding algorithm requiring a minimum of **5 Active Storage Nodes** (3 Data Shards + 2 Parity Shards).
Open 5 new terminal windows, activate the virtual environment in each, and run:

```bash
python apps/p2p/storage_node.py node-1 8001
python apps/p2p/storage_node.py node-2 8002
python apps/p2p/storage_node.py node-3 8003
python apps/p2p/storage_node.py node-4 8004
python apps/p2p/storage_node.py node-5 8005
```

## 5. Background Task Workers (Celery)

Start the Celery worker to perform the heavy lifting of Chunking, AES encryption, Merkle DAG building, and interacting with the P2P Nodes.
Open a new terminal window, activate the virtual environment, and run:

```bash
# Windows
celery -A aetherstore worker --pool=solo --loglevel=info

# Mac/Linux
celery -A aetherstore worker --loglevel=info
```

Your local AetherStore cluster is now fully functional! Proceed to the **API Documentation** to start storing objects.
