from django.core.management.base import BaseCommand
from django.conf import settings
from apps.storage.models import StorageNode
from django.utils import timezone
import asyncio
import aiohttp
from aiohttp import web
import os

class Command(BaseCommand):
    help = "Run storage node for shard storage and retrieval"
    
    def add_arguments(self, parser):
        parser.add_argument('--node-id', type=str, required=True)
        parser.add_argument('--port', type=int, default=8001)
    
    def handle(self, *args, **options):
        node_id = options['node_id']
        port = options['port']
        
        # Register node in database
        node, created = StorageNode.objects.update_or_create(
            node_id=node_id,
            defaults={
                'endpoint': f'http://localhost:{port}',
                'is_active': True,
                'last_heartbeat': timezone.now()
            }
        )
        
        self.stdout.write(self.style.SUCCESS(f'Storage node {node_id} registered'))
        
        # Run async HTTP server for shard operations
        asyncio.run(self.run_server(node_id, port))
    
    async def run_server(self, node_id, port):
        app = web.Application()
        app.router.add_put('/shard/{content_hash}/{shard_index}', self.store_shard)
        app.router.add_get('/shard/{content_hash}/{shard_index}', self.retrieve_shard)
        app.router.add_head('/shard/{content_hash}/{shard_index}', self.check_shard)
        app.router.add_get('/health', self.health_check)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        self.stdout.write(self.style.SUCCESS(f'Storage node listening on port {port}'))
        
        # Keep running
        while True:
            await asyncio.sleep(30)
            # Update heartbeat
            StorageNode.objects.filter(node_id=node_id).update(
                last_heartbeat=timezone.now()
            )
    
    async def store_shard(self, request):
        content_hash = request.match_info['content_hash']
        shard_index = request.match_info['shard_index']
        data = await request.read()
        
        # Store shard to disk
        shard_path = f"/data/{content_hash}/{shard_index}"
        os.makedirs(os.path.dirname(shard_path), exist_ok=True)
        
        with open(shard_path, 'wb') as f:
            f.write(data)
        
        return web.Response(status=200, text='Shard stored')
    
    async def retrieve_shard(self, request):
        content_hash = request.match_info['content_hash']
        shard_index = request.match_info['shard_index']
        
        shard_path = f"/data/{content_hash}/{shard_index}"
        
        if not os.path.exists(shard_path):
            return web.Response(status=404, text='Shard not found')
        
        with open(shard_path, 'rb') as f:
            data = f.read()
        
        return web.Response(body=data, content_type='application/octet-stream')
    
    async def check_shard(self, request):
        content_hash = request.match_info['content_hash']
        shard_index = request.match_info['shard_index']
        
        shard_path = f"/data/{content_hash}/{shard_index}"
        
        if os.path.exists(shard_path):
            return web.Response(status=200)
        else:
            return web.Response(status=404)
    
    async def health_check(self, request):
        return web.Response(status=200, text='OK')