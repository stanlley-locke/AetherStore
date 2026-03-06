#!/bin/bash

echo "========================================"
echo "AetherStore - Node Health Check"
echo "========================================"

# Check each node
for port in 8001 8002 8003; do
    echo -n "Node on port $port: "
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health 2>/dev/null)
    
    if [ "$response" = "200" ]; then
        echo "✓ Healthy"
    else
        echo "✗ Unreachable (HTTP $response)"
    fi
done

echo ""
echo "Checking via Django..."
python manage.py shell << 'PYEOF'
from apps.p2p.services.node_monitor import node_monitor

status = node_monitor.get_cluster_status()
print(f"\nCluster Status:")
print(f"  Total nodes: {status['total_nodes']}")
print(f"  Healthy: {status['healthy_nodes']}")
print(f"  Unhealthy: {status['unhealthy_nodes']}")
print(f"  Cluster healthy: {status['cluster_healthy']}")

if status['nodes']:
    print(f"\nHealthy nodes:")
    for node in status['nodes']:
        print(f"  ✓ {node['node_id']} ({node['endpoint']}) - {node['latency_ms']}ms")
PYEOF

echo ""
echo "========================================"
