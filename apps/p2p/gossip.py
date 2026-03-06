"""
Gossip Protocol for P2P Node Discovery
Uses central bootstrap node for initial peer discovery
Configuration loaded from JSON file
"""

import asyncio
import random
import time
import httpx
from typing import Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone
from channels.db import database_sync_to_async
from .peer_config import get_peer_config


class GossipProtocol:
    """Gossip-based peer discovery with bootstrap node"""
    
    def __init__(self, node_id: str, node_port: int):
        self.node_id = node_id
        self.node_port = node_port
        self.peers: Dict[str, dict] = {}
        self.state_version = 0
        
        # Load configuration
        self.config = get_peer_config()
        gossip_config = self.config.get_gossip_config()
        
        self.GOSSIP_INTERVAL = gossip_config.get('interval_seconds', 10)
        self.GOSSIP_FANOUT = gossip_config.get('fanout', 3)
        self.NODE_TIMEOUT = gossip_config.get('node_timeout_seconds', 60)
        self.MAX_PEERS = gossip_config.get('max_peers', 100)
    
    async def start(self):
        """Start gossip protocol"""
        print(f"Gossip protocol started for node {self.node_id}")
        print(f"Gossip interval: {self.GOSSIP_INTERVAL}s, Fanout: {self.GOSSIP_FANOUT}")
        
        # Initial bootstrap
        await self._bootstrap_from_config()
        
        while True:
            try:
                await self._gossip_cycle()
                await asyncio.sleep(self.GOSSIP_INTERVAL)
            except Exception as e:
                print(f"Gossip error: {e}")
                await asyncio.sleep(30)
    
    async def _bootstrap_from_config(self):
        """Bootstrap from configuration file"""
        print("Loading peer configuration...")
        
        # Get default peers from config
        default_peers = self.config.get_default_peers()
        
        for peer in default_peers:
            peer_id = peer.get('node_id')
            endpoint = peer.get('endpoint')
            
            if peer_id and peer_id != self.node_id:
                self.peers[peer_id] = {
                    'endpoint': endpoint,
                    'last_seen': time.time(),
                    'state': 'configured',
                    'version': 0
                }
                print(f"  ✓ Configured peer: {peer_id} at {endpoint}")
        
        # Try to contact bootstrap node
        bootstrap = self.config.get_bootstrap_node()
        if bootstrap and bootstrap.get('node_id') != self.node_id:
            await self._contact_bootstrap(bootstrap)
    
    async def _contact_bootstrap(self, bootstrap: dict):
        """Contact bootstrap node to get peer list"""
        try:
            endpoint = bootstrap.get('endpoint')
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{endpoint}/gossip",
                    json={
                        'node_id': self.node_id,
                        'endpoint': f'http://localhost:{self.node_port}',
                        'peers': [self.node_id],
                        'version': 0,
                        'timestamp': time.time(),
                        'action': 'bootstrap'
                    }
                )
                
                if response.status_code == 200:
                    their_state = response.json()
                    await self._merge_state(their_state)
                    print(f"Bootstrap successful from {bootstrap.get('node_id')}")
                else:
                    print(f"Bootstrap failed: {response.status_code}")
        
        except Exception as e:
            print(f"Bootstrap node unreachable: {e}")
    
    async def _gossip_cycle(self):
        """One cycle of gossip protocol"""
        await self._update_self_state()
        live_peers = self._get_live_peers()
        
        if not live_peers:
            # No live peers - try bootstrap again
            bootstrap = self.config.get_bootstrap_node()
            if bootstrap:
                await self._contact_bootstrap(bootstrap)
            return
        
        # Select random peers to gossip with
        selected_peers = random.sample(
            live_peers, 
            min(self.GOSSIP_FANOUT, len(live_peers))
        )
        
        # Exchange state with selected peers
        await self._exchange_state(selected_peers)
        
        # Detect dead nodes
        await self._detect_dead_nodes()
    
    @database_sync_to_async
    def _update_self_state(self):
        """Update own node state in database"""
        from apps.storage.models import StorageNode
        
        StorageNode.objects.update_or_create(
            node_id=self.node_id,
            defaults={
                'endpoint': f'http://localhost:{self.node_port}',
                'is_active': True,
                'last_heartbeat': timezone.now()
            }
        )
        
        self.peers[self.node_id] = {
            'endpoint': f'http://localhost:{self.node_port}',
            'last_seen': time.time(),
            'state': 'alive',
            'version': self.state_version
        }
    
    def _get_live_peers(self) -> List[str]:
        """Get list of live peer node IDs"""
        live = []
        current_time = time.time()
        
        for node_id, state in self.peers.items():
            if node_id == self.node_id:
                continue
            if current_time - state['last_seen'] < self.NODE_TIMEOUT:
                live.append(node_id)
        
        return live
    
    async def _exchange_state(self, peer_ids: List[str]):
        """Exchange state with selected peers"""
        async with httpx.AsyncClient(timeout=5.0) as client:
            for peer_id in peer_ids:
                try:
                    peer_state = self.peers.get(peer_id, {})
                    endpoint = peer_state.get('endpoint')
                    
                    if not endpoint:
                        continue
                    
                    our_state = {
                        'node_id': self.node_id,
                        'endpoint': f'http://localhost:{self.node_port}',
                        'peers': list(self.peers.keys())[:self.MAX_PEERS],
                        'version': self.state_version,
                        'timestamp': time.time()
                    }
                    
                    response = await client.post(
                        f"{endpoint}/gossip",
                        json=our_state
                    )
                    
                    if response.status_code == 200:
                        their_state = response.json()
                        await self._merge_state(their_state)
                        self.peers[peer_id]['last_seen'] = time.time()
                        self.peers[peer_id]['state'] = 'alive'
                    
                except Exception as e:
                    print(f"Gossip with {peer_id} failed: {e}")
                    self.peers[peer_id]['state'] = 'unreachable'
    
    async def _merge_state(self, remote_state: dict):
        """Merge remote state with local state"""
        remote_peers = remote_state.get('peers', [])
        remote_endpoint = remote_state.get('endpoint')
        remote_node_id = remote_state.get('node_id')
        
        # Update endpoint for remote node
        if remote_node_id and remote_node_id in self.peers:
            self.peers[remote_node_id]['endpoint'] = remote_endpoint
        
        # Discover new peers
        for peer_id in remote_peers:
            if peer_id not in self.peers and len(self.peers) < self.MAX_PEERS:
                self.peers[peer_id] = {
                    'endpoint': f'http://localhost:8001',  # Will be updated on contact
                    'last_seen': time.time(),
                    'state': 'discovered',
                    'version': remote_state.get('version', 0)
                }
                print(f"Discovered peer: {peer_id}")
        
        self.state_version = max(self.state_version, remote_state.get('version', 0)) + 1
    
    async def _detect_dead_nodes(self):
        """Detect and mark dead nodes"""
        current_time = time.time()
        dead_nodes = []
        
        for node_id, state in self.peers.items():
            if current_time - state['last_seen'] > self.NODE_TIMEOUT:
                if state['state'] != 'dead':
                    state['state'] = 'dead'
                    dead_nodes.append(node_id)
                    print(f"Node {node_id} marked as dead")
        
        if dead_nodes:
            await self._update_dead_nodes(dead_nodes)
    
    @database_sync_to_async
    def _update_dead_nodes(self, dead_node_ids: List[str]):
        """Update dead nodes in database"""
        from apps.storage.models import StorageNode
        
        StorageNode.objects.filter(
            node_id__in=dead_node_ids
        ).update(is_active=False)
        
        # Trigger repair for affected shards
        self._trigger_repair_sync(dead_node_ids)
    
    def _trigger_repair_sync(self, dead_node_ids: List[str]):
        """Trigger repair tasks for affected shards"""
        from workers.auditor import repair_object
        from apps.storage.models import StorageObject
        
        for node_id in dead_node_ids:
            affected_objects = StorageObject.objects.filter(
                shard_map__has_key=node_id,
                is_deleted=False
            )
            
            for obj in affected_objects:
                repair_object.delay(str(obj.id))
                print(f"Triggered repair for object {obj.id}")


# Gossip endpoint handler for Django views
def gossip_handler(request):
    """Handle incoming gossip messages (sync Django view)"""
    import json
    from django.http import JsonResponse
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Log gossip received
            node_id = data.get('node_id')
            action = data.get('action', 'gossip')
            peer_count = len(data.get('peers', []))
            
            print(f"Gossip from {node_id} (action: {action}, peers: {peer_count})")
            
            # Return our state
            from apps.storage.models import StorageNode
            nodes = StorageNode.objects.filter(is_active=True)
            peer_list = [n.node_id for n in nodes if n.node_id != node_id]
            
            return JsonResponse({
                'status': 'received',
                'node_id': 'bootstrap-1',  # This node acts as bootstrap
                'peers': peer_list,
                'version': 1
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

