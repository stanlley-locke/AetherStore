"""
Storage Node Monitoring Service
Health checks and availability tracking for storage nodes
"""

import urllib.request
import urllib.error
import logging
import time
from typing import Dict, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class NodeMonitor:
    """Monitor storage node health and availability"""
    
    def __init__(self):
        self.timeout = 5  # seconds
    
    def check_node_health(self, node_id: str, endpoint: str) -> Dict:
        """Check health of a single node"""
        result = {
            'node_id': node_id,
            'endpoint': endpoint,
            'healthy': False,
            'latency_ms': None,
            'error': None,
            'stats': None
        }
        
        try:
            start = time.time()
            
            # Simple urllib request (no SSL issues)
            url = f"{endpoint}/health"
            req = urllib.request.Request(url, method='GET')
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                elapsed = (time.time() - start) * 1000
                result['latency_ms'] = round(elapsed, 2)
                
                if response.status == 200:
                    result['healthy'] = True
                    import json
                    result['stats'] = json.loads(response.read().decode('utf-8'))
                else:
                    result['error'] = f"HTTP {response.status}"
                    
        except urllib.error.URLError as e:
            result['error'] = f"Connection failed: {str(e.reason)}"
        except urllib.error.HTTPError as e:
            result['error'] = f"HTTP {e.code}"
        except TimeoutError:
            result['error'] = f"Timeout after {self.timeout}s"
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def get_healthy_nodes(self, min_count: int = 3) -> List[Dict]:
        """Get list of healthy nodes (Async to support DHT lookup)"""
        from apps.core.dht import dht_service
        from apps.storage.models import StorageNode
        
        dht_node = dht_service.get_node()
        
        # 1. Active Discovery: Query DHT to find all nodes in the network
        logger.info("[Monitor] Performing recursive DHT discovery...")
        await dht_node.find_node(dht_node.node_id)
        
        peers = dht_node.find_closest_peers(dht_node.node_id, count=20)
        healthy_nodes = []
        
        # 2. Query DHT For Peers
        for peer in peers:
            endpoint = f"http://{peer.address}:{peer.port}"
            health = self.check_node_health(peer.node_id, endpoint)
            
            if health['healthy']:
                healthy_nodes.append({
                    'node_id': peer.node_id,
                    'endpoint': endpoint,
                    'latency_ms': health['latency_ms'],
                    'stats': health['stats']
                })
        
        # 3. Fallback to Centralized DB if DHT lacks peers (e.g., initial bootstrap)
        if len(healthy_nodes) < min_count:
            from asgiref.sync import sync_to_async
            
            # Use sync_to_async to safely query the ORM from an async context
            get_active_nodes = sync_to_async(lambda: list(StorageNode.objects.filter(is_active=True)))
            nodes = await get_active_nodes()
            
            for node in nodes:
                if any(n['node_id'] == node.node_id for n in healthy_nodes):
                    continue
                    
                health = self.check_node_health(node.node_id, node.endpoint)
                
                if health['healthy']:
                    async def update_heartbeat(n):
                        n.last_heartbeat = timezone.now()
                        n.save(update_fields=['last_heartbeat'])
                    
                    await sync_to_async(update_heartbeat)(node)
                    
                    healthy_nodes.append({
                        'node_id': node.node_id,
                        'endpoint': node.endpoint,
                        'latency_ms': health['latency_ms'],
                        'stats': health['stats']
                    })
                else:
                    logger.warning(f"Node {node.node_id} unhealthy: {health['error']}")
                    # Don't deactivate yet, could be a networking blip
        
        return healthy_nodes
    
    async def verify_enough_nodes(self, required_count: int = 3) -> Dict:
        """Verify we have enough healthy nodes"""
        healthy_nodes = await self.get_healthy_nodes(required_count)
        
        return {
            'success': len(healthy_nodes) >= required_count,
            'available_nodes': len(healthy_nodes),
            'required_nodes': required_count,
            'nodes': healthy_nodes,
            'message': f"{len(healthy_nodes)} nodes available" if len(healthy_nodes) >= required_count 
                      else f"Only {len(healthy_nodes)} nodes available, need {required_count}"
        }
    
    def activate_healthy_nodes(self):
        """Re-activate nodes that are now healthy"""
        from apps.storage.models import StorageNode
        
        inactive_nodes = StorageNode.objects.filter(is_active=False)
        
        for node in inactive_nodes:
            health = self.check_node_health(node.node_id, node.endpoint)
            
            if health['healthy']:
                node.is_active = True
                node.last_heartbeat = timezone.now()
                node.save(update_fields=['is_active', 'last_heartbeat'])
                logger.info(f"Node {node.node_id} reactivated")
    
    async def get_cluster_status(self) -> Dict:
        """Get overall cluster health status"""
        from apps.storage.models import StorageNode
        from asgiref.sync import sync_to_async
        
        # Use sync_to_async for DB count
        get_count = sync_to_async(lambda: StorageNode.objects.count())
        total_nodes = await get_count()
        
        healthy_nodes = await self.get_healthy_nodes()
        
        return {
            'total_nodes': total_nodes,
            'healthy_nodes': len(healthy_nodes),
            'unhealthy_nodes': total_nodes - len(healthy_nodes),
            'cluster_healthy': len(healthy_nodes) >= 3,
            'nodes': healthy_nodes
        }


# Singleton
node_monitor = NodeMonitor()
