from django.core.management.base import BaseCommand
import asyncio
import sys

class Command(BaseCommand):
    help = 'Run P2P storage node server'
    
    def add_arguments(self, parser):
        parser.add_argument('--node-id', type=str, required=True, help='Unique node identifier')
        parser.add_argument('--port', type=int, default=8001, help='Port to listen on')
        parser.add_argument('--storage-path', type=str, default='./data/shards', help='Path to store shards')
    
    def handle(self, *args, **options):
        node_id = options['node_id']
        port = options['port']
        storage_path = options['storage_path']
        
        self.stdout.write(self.style.SUCCESS(f'Starting storage node {node_id} on port {port}'))
        
        # Import and run storage node server
        from apps.p2p.storage_node import StorageNodeServer
        
        server = StorageNodeServer(node_id, port, storage_path)
        
        # Register node in database
        from apps.storage.models import StorageNode
        from django.utils import timezone
        
        StorageNode.objects.update_or_create(
            node_id=node_id,
            defaults={
                'endpoint': f'http://localhost:{port}',
                'is_active': True,
                'last_heartbeat': timezone.now()
            }
        )
        
        self.stdout.write(self.style.SUCCESS(f'Node {node_id} registered in database'))
        
        # Start gossip protocol
        from apps.p2p.gossip import GossipProtocol
        
        gossip = GossipProtocol(node_id, port)
        
        # Run both server and gossip
        async def run_all():
            # Start gossip in background
            gossip_task = asyncio.create_task(gossip.start())
            
            # Start storage server
            try:
                await server.start()
            finally:
                gossip_task.cancel()
        
        try:
            asyncio.run(run_all())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING(f'\nNode {node_id} stopped'))
