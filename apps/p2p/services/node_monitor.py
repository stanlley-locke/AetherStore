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
    
    def get_healthy_nodes(self, min_count: int = 3) -> List[Dict]:
        """Get list of healthy nodes"""
        from apps.storage.models import StorageNode
        
        nodes = StorageNode.objects.filter(is_active=True)
        healthy_nodes = []
        
        for node in nodes:
            health = self.check_node_health(node.node_id, node.endpoint)
            
            if health['healthy']:
                healthy_nodes.append({
                    'node_id': node.node_id,
                    'endpoint': node.endpoint,
                    'latency_ms': health['latency_ms'],
                    'stats': health['stats']
                })
            else:
                logger.warning(f"Node {node.node_id} unhealthy: {health['error']}")
                node.is_active = False
                node.save(update_fields=['is_active'])
        
        return healthy_nodes
    
    def verify_enough_nodes(self, required_count: int = 3) -> Dict:
        """Verify we have enough healthy nodes"""
        healthy_nodes = self.get_healthy_nodes(required_count)
        
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
    
    def get_cluster_status(self) -> Dict:
        """Get overall cluster health status"""
        from apps.storage.models import StorageNode
        
        all_nodes = StorageNode.objects.all()
        healthy_nodes = self.get_healthy_nodes()
        
        return {
            'total_nodes': all_nodes.count(),
            'healthy_nodes': len(healthy_nodes),
            'unhealthy_nodes': all_nodes.count() - len(healthy_nodes),
            'cluster_healthy': len(healthy_nodes) >= 3,
            'nodes': healthy_nodes
        }


# Singleton
node_monitor = NodeMonitor()
