#!/bin/bash
set -e

# Function to wait for a service to be ready
wait_for_service() {
    local host="$1"
    local port="$2"
    local name="$3"
    
    echo "Waiting for $name ($host:$port)..."
    while ! nc -z "$host" "$port"; do
      sleep 1
    done
    echo "$name is up!"
}

# Default values
SERVICE_TYPE=${SERVICE_TYPE:-"web"}

# Wait for database if we are running a backend service
if [[ "$SERVICE_TYPE" == "web" || "$SERVICE_TYPE" == "worker" || "$SERVICE_TYPE" == "beat" ]]; then
    if [ -n "$DB_HOST" ]; then
        wait_for_service "$DB_HOST" "${DB_PORT:-5432}" "Database"
    fi
fi

# Wait for redis
if [ -n "$REDIS_HOST" ]; then
    wait_for_service "$REDIS_HOST" "${REDIS_PORT:-6379}" "Redis"
fi

if [[ "$SERVICE_TYPE" == "web" ]]; then
    echo "Running migrations..."
    python manage.py migrate --noinput
    
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
    
    echo "Initializing Network Admin (if needed)..."
    python scripts/init_network_admin.py || echo "Network admin initialization failed or already exists"
    
    echo "Starting Gunicorn..."
    # Using uvicorn worker for Channels/ASGI support
    exec uvicorn aetherstore.asgi:application --host 0.0.0.0 --port 8000 --workers 4
    
elif [[ "$SERVICE_TYPE" == "worker" ]]; then
    echo "Starting Celery Worker..."
    exec celery -A aetherstore worker --loglevel=info
    
elif [[ "$SERVICE_TYPE" == "beat" ]]; then
    echo "Starting Celery Beat..."
    # Remove old schedule file to avoid sync issues
    rm -f celerybeat-schedule
    exec celery -A aetherstore beat --loglevel=info
    
elif [[ "$SERVICE_TYPE" == "node" ]]; then
    echo "Starting Storage Node ${NODE_ID:-node-1} on port ${NODE_PORT:-8001}..."
    mkdir -p data/shards
    
    BOOTSTRAP_ARG=""
    if [ -n "$BOOTSTRAP_NODE" ]; then
        BOOTSTRAP_ARG="--bootstrap $BOOTSTRAP_NODE"
    fi
    
    WALLET_ARG=""
    if [ -n "$NODE_WALLET_ADDRESS" ]; then
        WALLET_ARG="--wallet-address $NODE_WALLET_ADDRESS"
    fi
    
    exec python apps/p2p/storage_node.py "${NODE_ID:-node-1}" "${NODE_PORT:-8001}" $BOOTSTRAP_ARG $WALLET_ARG
    
else
    echo "Unknown SERVICE_TYPE: $SERVICE_TYPE"
    exit 1
fi
