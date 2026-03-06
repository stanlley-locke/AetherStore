"""
Consistent Hash Ring for Shard Distribution
"""

import hashlib
from typing import Dict, List, Tuple
from django.core.cache import cache
from apps.storage.models import StorageNode
import bisect


class ConsistentHashRing:
    """Consistent hashing with virtual nodes"""
    
    VIRTUAL_NODES = 100  # Virtual nodes per physical node
    CACHE_KEY = 'aether:hash_ring'
    CACHE_TTL = 60
    
    def __init__(self):
        self.ring: List[Tuple[int, str]] = []
        self.sorted_keys: List[int] = []
        self.nodes: Dict[str, str] = {}
        self._load_or_build()
    
    def _hash(self, key: str) -> int:
        """Generate consistent hash for key"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def _load_or_build(self):
        """Load ring from cache or rebuild"""
        cached = cache.get(self.CACHE_KEY)
        
        if cached:
            self.ring = cached.get('ring', [])
            self.sorted_keys = cached.get('keys', [])
            self.nodes = cached.get('nodes', {})
        else:
            self._rebuild()
    
    def _rebuild(self):
        """Rebuild hash ring from database"""
        self.ring = []
        self.nodes = {}
        
        # Get active nodes
        nodes = StorageNode.objects.filter(is_active=True)
        
        for node in nodes:
            self.nodes[node.node_id] = node.endpoint
            
            # Add virtual nodes
            for i in range(self.VIRTUAL_NODES):
                virtual_key = f"{node.node_id}:vn{i}"
                hash_value = self._hash(virtual_key)
                self.ring.append((hash_value, node.node_id))
        
        # Sort ring
        self.ring.sort(key=lambda x: x[0])
        self.sorted_keys = [h for h, _ in self.ring]
        
        # Cache
        cache.set(self.CACHE_KEY, {
            'ring': self.ring,
            'keys': self.sorted_keys,
            'nodes': self.nodes
        }, self.CACHE_TTL)
    
    def get_nodes_for_shard(self, content_hash: str, shard_index: int, replicas: int = 1) -> List[Tuple[str, str]]:
        """Get nodes responsible for a shard"""
        if not self.ring:
            self._rebuild()
        
        if not self.nodes:
            return []
        
        # Create unique key for this shard
        shard_key = f"{content_hash}:shard:{shard_index}"
        hash_value = self._hash(shard_key)
        
        # Find position in ring
        idx = bisect.bisect_right(self.sorted_keys, hash_value)
        if idx >= len(self.sorted_keys):
            idx = 0
        
        # Collect unique nodes
        result = []
        seen = set()
        start_idx = idx
        
        while len(result) < replicas and len(seen) < len(self.nodes):
            _, node_id = self.ring[idx]
            
            if node_id not in seen and node_id in self.nodes:
                seen.add(node_id)
                result.append((node_id, self.nodes[node_id]))
            
            idx = (idx + 1) % len(self.ring)
            
            if idx == start_idx:
                break
        
        return result
    
    def get_all_nodes_for_object(self, content_hash: str, total_shards: int, replicas: int = 2) -> Dict[int, List[Tuple[str, str]]]:
        """
        Get nodes for all shards of an object.
        Ensures that primary nodes for shards are distributed to distinct physical nodes
        to avoid multiple shards landing on the same node and triggering upload faults.
        
        Args:
            content_hash: The root hash or chunk hash
            total_shards: Total number of shards (e.g. 5)
            replicas: Number of fallback replica nodes per shard (default 2)
        """
        if not self.ring:
            self._rebuild()
            
        if not self.nodes:
            return {}
            
        # Hash the object key ONCE to find a base starting point
        hash_value = self._hash(content_hash)
        
        idx = bisect.bisect_right(self.sorted_keys, hash_value)
        if idx >= len(self.sorted_keys):
            idx = 0
            
        shard_map = {}
        distinct_nodes_found = []
        seen_node_ids = set()
        seen_endpoints = set()
        
        # Traverse the ring to establish a sequence of distinct physical nodes (by endpoint)
        start_idx = idx
        
        # Count total unique endpoints in the ring so we know when to stop
        total_unique_endpoints = len(set(self.nodes.values()))
        
        while len(distinct_nodes_found) < total_unique_endpoints:
            _, node_id = self.ring[idx]
            
            if node_id in self.nodes:
                endpoint = self.nodes[node_id]
                
                if node_id not in seen_node_ids and endpoint not in seen_endpoints:
                    seen_node_ids.add(node_id)
                    seen_endpoints.add(endpoint)
                    distinct_nodes_found.append((node_id, endpoint))
                
            idx = (idx + 1) % len(self.ring)
            if idx == start_idx:
                break
                
        # Now round-robin distribute the shards across the available distinct nodes.
        # This guarantees shard 0 -> node A, shard 1 -> node B, etc.
        for i in range(total_shards):
            shard_nodes = []
            
            # Start index for this shard shifts by `i` to stagger primaries
            for r in range(replicas):
                node_idx = (i + r) % len(distinct_nodes_found)
                node = distinct_nodes_found[node_idx]
                shard_nodes.append(node)
                
            shard_map[i] = shard_nodes
            
        return shard_map
    
    def invalidate(self):
        """Invalidate cache"""
        cache.delete(self.CACHE_KEY)
        self._load_or_build()


# Singleton
_hash_ring = None

def get_hash_ring() -> ConsistentHashRing:
    """Get singleton hash ring instance"""
    global _hash_ring
    if _hash_ring is None:
        _hash_ring = ConsistentHashRing()
    return _hash_ring
