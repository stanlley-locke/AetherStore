"""
Distributed Hash Table Implementation
Kademlia-based DHT for decentralized peer discovery
"""

import hashlib
import time
import random
import asyncio
import os
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import OrderedDict
import json
import httpx


@dataclass
class Peer:
    """Represents a peer in the DHT"""
    node_id: str
    address: str
    port: int
    last_seen: float = field(default_factory=time.time)
    reputation: float = 50.0
    latency_ms: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'node_id': self.node_id,
            'address': self.address,
            'port': self.port,
            'last_seen': self.last_seen,
            'reputation': self.reputation,
            'latency_ms': self.latency_ms
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Peer':
        return cls(**data)


class KBucket:
    """K-Bucket for storing peer information (Kademlia)"""
    
    K = 20  # Bucket size (configurable)
    
    def __init__(self, prefix: str):
        self.prefix = prefix
        self.peers: OrderedDict[str, Peer] = OrderedDict()
    
    def add_peer(self, peer: Peer) -> bool:
        """Add peer to bucket, return True if added"""
        if peer.node_id in self.peers:
            # Update existing
            self.peers.move_to_end(peer.node_id)
            self.peers[peer.node_id] = peer
            return True
        
        if len(self.peers) >= self.K:
            # Bucket full, remove oldest (LRU)
            self.peers.popitem(last=False)
        
        self.peers[peer.node_id] = peer
        return True
    
    def remove_peer(self, node_id: str) -> bool:
        """Remove peer from bucket"""
        if node_id in self.peers:
            del self.peers[node_id]
            return True
        return False
    
    def get_peers(self, count: int = None) -> List[Peer]:
        """Get peers from bucket"""
        peers = list(self.peers.values())
        if count:
            return peers[:count]
        return peers
    
    def __len__(self) -> int:
        return len(self.peers)


class DHTNode:
    """
    DHT Node Implementation
    Kademlia-based distributed hash table for peer discovery and data location
    """
    
    ID_BITS = 160  # SHA-1 produces 160-bit hashes
    
    def __init__(self, node_id: str = None, address: str = 'localhost', port: int = 8001):
        self.node_id = node_id or self._generate_node_id()
        self.address = address
        self.port = port
        self.buckets: Dict[int, KBucket] = {}
        self.data_store: Dict[str, Dict] = {}
        self.peers: Dict[str, Peer] = {}
        
        # Initialize 160 buckets (for 160-bit node IDs)
        for i in range(self.ID_BITS):
            self.buckets[i] = KBucket(f'{i}')
        
        # Add self to peers
        self.peers[self.node_id] = Peer(
            node_id=self.node_id,
            address=self.address,
            port=self.port
        )
    
    def _generate_node_id(self) -> str:
        """Generate random 160-bit node ID"""
        return hashlib.sha1(f'{time.time()}{random.random()}{os.urandom(16)}'.encode()).hexdigest()
    
    def _distance(self, id1: str, id2: str) -> int:
        """Calculate XOR distance between two node IDs"""
        return int(id1, 16) ^ int(id2, 16)
    
    def _bucket_index(self, node_id: str) -> int:
        """Determine which bucket a node ID belongs to"""
        distance = self._distance(self.node_id, node_id)
        if distance == 0:
            return 0
        return min(distance.bit_length() - 1, self.ID_BITS - 1)
    
    def add_peer(self, peer: Peer):
        """Add peer to appropriate bucket"""
        if peer.node_id == self.node_id:
            return
        
        bucket_index = self._bucket_index(peer.node_id)
        self.buckets[bucket_index].add_peer(peer)
        self.peers[peer.node_id] = peer
    
    def remove_peer(self, node_id: str):
        """Remove peer from DHT"""
        if node_id in self.peers:
            bucket_index = self._bucket_index(node_id)
            self.buckets[bucket_index].remove_peer(node_id)
            del self.peers[node_id]
    
    def find_closest_peers(self, target_id: str, count: int = 20) -> List[Peer]:
        """Find K closest peers to target ID"""
        all_peers = []
        for bucket in self.buckets.values():
            all_peers.extend(bucket.get_peers())
        
        # Remove self
        all_peers = [p for p in all_peers if p.node_id != self.node_id]
        
        # Sort by distance to target
        all_peers.sort(key=lambda p: self._distance(target_id, p.node_id))
        
        return all_peers[:count]
    
    def store(self, key: str, value: Any, ttl: int = 3600, replicate: bool = True):
        """
        Store key-value pair in DHT
        
        Args:
            key: Key to store
            value: Value to store
            ttl: Time to live in seconds
            replicate: Whether to replicate to closest nodes
        """
        self.data_store[key] = {
            'value': value,
            'expires': time.time() + ttl,
            'publisher': self.node_id,
            'created_at': time.time()
        }
        
        # In production, replicate to K closest nodes
        if replicate:
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self._replicate(key, value, ttl))
            except RuntimeError:
                # No event loop, run synchronously
                asyncio.run(self._replicate(key, value, ttl))
    
    async def _replicate(self, key: str, value: Any, ttl: int):
        """Replicate data to closest nodes"""
        closest = self.find_closest_peers(key, count=3)
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            for peer in closest:
                try:
                    await client.post(
                        f"http://{peer.address}:{peer.port}/dht/store",
                        json={
                            'key': key,
                            'value': value,
                            'ttl': ttl,
                            'publisher': self.node_id
                        }
                    )
                except Exception:
                    continue
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from local DHT store"""
        if key not in self.data_store:
            return None
        
        entry = self.data_store[key]
        if time.time() > entry['expires']:
            del self.data_store[key]
            return None
        
        return entry['value']
    
    async def find_value(self, key: str) -> Optional[Any]:
        """
        Find value in DHT by querying peers
        
        Args:
            key: Key to search for
            
        Returns:
            Value if found, None otherwise
        """
        # Check local store first
        local_value = self.get(key)
        if local_value:
            return local_value
        
        # Query closest peers
        closest = self.find_closest_peers(key, count=5)
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            for peer in closest:
                try:
                    response = await client.get(
                        f"http://{peer.address}:{peer.port}/dht/get/{key}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('found'):
                            return data.get('value')
                except Exception:
                    continue
        
        return None
    
    def store_shard_location(self, content_hash: str, chunk_index: int, 
                            shard_index: int, node_id: str):
        """Store shard location in DHT"""
        key = f'shard:{content_hash}:{chunk_index}:{shard_index}'
        self.store(key, {
            'node_id': node_id,
            'timestamp': time.time(),
            'content_hash': content_hash,
            'chunk_index': chunk_index,
            'shard_index': shard_index
        })
    
    async def find_shard(self, content_hash: str, chunk_index: int, 
                        shard_index: int) -> Optional[str]:
        """Find node storing specific shard"""
        key = f'shard:{content_hash}:{chunk_index}:{shard_index}'
        result = await self.find_value(key)
        
        if result:
            return result.get('node_id')
        return None
    
    async def find_all_shards(self, content_hash: str, chunk_count: int, 
                             shards_per_chunk: int) -> Dict[str, List[str]]:
        """
        Find all nodes storing shards for a file
        
        Returns:
            Dict of chunk_index:shard_index -> [node_ids]
        """
        locations = {}
        
        for chunk_idx in range(chunk_count):
            for shard_idx in range(shards_per_chunk):
                node_id = await self.find_shard(content_hash, chunk_idx, shard_idx)
                if node_id:
                    key = f"{chunk_idx}:{shard_idx}"
                    locations[key] = [node_id]
        
        return locations
    
    def get_routing_table_stats(self) -> Dict:
        """Get DHT routing table statistics"""
        total_peers = sum(len(bucket.peers) for bucket in self.buckets.values())
        non_empty_buckets = sum(1 for bucket in self.buckets.values() if bucket.peers)
        
        return {
            'node_id': self.node_id,
            'address': self.address,
            'port': self.port,
            'total_peers': total_peers,
            'non_empty_buckets': non_empty_buckets,
            'total_buckets': len(self.buckets),
            'stored_keys': len(self.data_store),
            'uptime_seconds': time.time() - self.peers[self.node_id].last_seen
        }
    
    def bootstrap(self, bootstrap_nodes: List[Dict]):
        """
        Bootstrap DHT by connecting to known nodes
        
        Args:
            bootstrap_nodes: List of {node_id, address, port} dicts
        """
        for node_info in bootstrap_nodes:
            peer = Peer(
                node_id=node_info['node_id'],
                address=node_info['address'],
                port=node_info['port']
            )
            self.add_peer(peer)


class DHTService:
    """Singleton service for DHT operations"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.node = None
            cls._instance.initialized = False
        return cls._instance
    
    def initialize(self, node_id: str = None, address: str = 'localhost', 
                  port: int = 8001, bootstrap_nodes: List[Dict] = None) -> DHTNode:
        """Initialize DHT node"""
        if not self.initialized:
            self.node = DHTNode(node_id, address, port)
            
            if bootstrap_nodes:
                self.node.bootstrap(bootstrap_nodes)
            
            self.initialized = True
        
        return self.node
    
    def get_node(self) -> DHTNode:
        """Get DHT node instance"""
        if not self.node:
            self.initialize()
        return self.node
    
    def store_shard_location(self, content_hash: str, chunk_index: int, 
                            shard_index: int, node_id: str):
        """Store shard location in DHT"""
        self.node.store_shard_location(
            content_hash, chunk_index, shard_index, node_id
        )
    
    async def find_shard(self, content_hash: str, chunk_index: int, 
                        shard_index: int) -> Optional[str]:
        """Find node storing specific shard"""
        return await self.node.find_shard(
            content_hash, chunk_index, shard_index
        )
    
    async def find_all_shards(self, content_hash: str, chunk_count: int, 
                             shards_per_chunk: int) -> Dict[str, List[str]]:
        """Find all nodes storing shards for a file"""
        return await self.node.find_all_shards(
            content_hash, chunk_count, shards_per_chunk
        )


# Global instance
dht_service = DHTService()