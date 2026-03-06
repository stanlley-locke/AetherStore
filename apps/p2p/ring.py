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
    
    def get_all_nodes_for_object(self, content_hash: str, total_shards: int) -> Dict[int, List[Tuple[str, str]]]:
        """Get all nodes for all shards of an object"""
        shard_map = {}
        
        for i in range(total_shards):
            # Get 2 replicas per shard for redundancy
            shard_map[i] = self.get_nodes_for_shard(content_hash, i, replicas=2)
        
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
