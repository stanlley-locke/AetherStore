"""
P2P Storage Node Server with Comprehensive Logging
Handles shard storage and retrieval with async I/O
Supports chunk-based Merkle DAG storage
"""

import asyncio
import aiofiles
from aiohttp import web
import hashlib
import json
import logging
import psutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class StorageNodeServer:
    """
    Async HTTP server for shard storage operations
    
    Features:
    - Chunk-based shard storage for Merkle DAG support
    - Comprehensive logging for all operations
    - Health checks with system metrics
    - Gossip protocol for peer discovery
    - Range request support for partial downloads
    - Storage statistics and monitoring
    """
    
    def __init__(self, node_id: str, port: int, storage_path: str = './data/shards'):
        self.node_id = node_id
        self.port = port
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.app = web.Application()
        self._setup_routes()
        
        # Metrics
        self.stats = {
            'uploads': 0,
            'downloads': 0,
            'deletes': 0,
            'errors': 0,
            'total_bytes_received': 0,
            'total_bytes_sent': 0,
            'started_at': datetime.now().isoformat()
        }
        
        logger.info(f"Initializing storage node {node_id} on port {port}")
        logger.info(f"Storage path: {self.storage_path.absolute()}")
    
    def _setup_routes(self):
        # NEW: Chunk-based URLs for Merkle DAG support
        self.app.router.add_put('/shard/{content_hash}/{chunk_index}/{shard_index}', self.store_shard)
        self.app.router.add_get('/shard/{content_hash}/{chunk_index}/{shard_index}', self.retrieve_shard)
        self.app.router.add_delete('/shard/{content_hash}/{chunk_index}/{shard_index}', self.delete_shard)
        
        # Legacy: Backwards compatible URLs (defaults to chunk 0)
        self.app.router.add_put('/shard/{content_hash}/{shard_index}', self.store_shard_legacy)
        self.app.router.add_get('/shard/{content_hash}/{shard_index}', self.retrieve_shard_legacy)
        
        # Management endpoints
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/stats', self.get_stats)
        self.app.router.add_get('/metrics', self.get_metrics)
        self.app.router.add_post('/gossip', self.gossip_handler)
        self.app.router.add_get('/shards', self.list_shards)
        self.app.router.add_delete('/shards/{content_hash}', self.delete_all_shards)
    
    #  UPLOAD ENDPOINTS 
    
    async def store_shard(self, request: web.Request) -> web.Response:
        """Store a shard with chunk_index support (NEW)"""
        client_ip = request.remote
        content_hash = request.match_info['content_hash']
        chunk_index = request.match_info['chunk_index']
        shard_index = request.match_info['shard_index']
        
        return await self._store_shard_impl(client_ip, content_hash, chunk_index, shard_index, request)
    
    async def store_shard_legacy(self, request: web.Request) -> web.Response:
        """Store a shard (legacy URL pattern, defaults to chunk 0)"""
        client_ip = request.remote
        content_hash = request.match_info['content_hash']
        shard_index = request.match_info['shard_index']
        
        return await self._store_shard_impl(client_ip, content_hash, '0', shard_index, request)
    
    async def _store_shard_impl(self, client_ip: str, content_hash: str, chunk_index: str, shard_index: str, request: web.Request) -> web.Response:
        """Implementation for storing shards"""
        logger.info(f"[UPLOAD] Receiving shard from {client_ip}")
        logger.info(f"[UPLOAD] Hash: {content_hash[:16]}... Chunk: {chunk_index}, Shard: {shard_index}")
        
        start_time = datetime.now()
        
        try:
            data = await request.read()
            actual_hash = hashlib.sha256(data).hexdigest()
            
            logger.info(f"[UPLOAD] Received {len(data)} bytes")
            
            # Create directory structure: hash/chunk_index/shard_index.shard
            shard_dir = self.storage_path / content_hash / chunk_index
            shard_dir.mkdir(parents=True, exist_ok=True)
            shard_path = shard_dir / f"{shard_index}.shard"
            
            # Write shard data
            async with aiofiles.open(shard_path, 'wb') as f:
                await f.write(data)
            
            # Store metadata
            metadata = {
                'content_hash': content_hash,
                'chunk_index': chunk_index,
                'shard_index': shard_index,
                'size': len(data),
                'hash': actual_hash,
                'node_id': self.node_id,
                'stored_at': datetime.now().isoformat(),
                'received_from': client_ip
            }
            
            metadata_path = shard_dir / f"{shard_index}.meta"
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(json.dumps(metadata, indent=2))
            
            # Update stats
            self.stats['uploads'] += 1
            self.stats['total_bytes_received'] += len(data)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"[UPLOAD] ✓ Stored in {elapsed:.3f}s | Path: {shard_path}")
            
            return web.json_response({
                'status': 'stored',
                'content_hash': content_hash,
                'chunk_index': chunk_index,
                'shard_index': shard_index,
                'size': len(data),
                'node_id': self.node_id,
                'elapsed_ms': round(elapsed * 1000, 2)
            })
            
        except Exception as e:
            self.stats['errors'] += 1
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"[UPLOAD] ✗ Failed: {e} ({elapsed:.3f}s)")
            return web.json_response({'error': str(e)}, status=500)
    
    #  DOWNLOAD ENDPOINTS 
    
    async def retrieve_shard(self, request: web.Request) -> web.Response:
        """Retrieve a shard with chunk_index support (NEW)"""
        client_ip = request.remote
        content_hash = request.match_info['content_hash']
        chunk_index = request.match_info['chunk_index']
        shard_index = request.match_info['shard_index']
        
        return await self._retrieve_shard_impl(client_ip, content_hash, chunk_index, shard_index, request)
    
    async def retrieve_shard_legacy(self, request: web.Request) -> web.Response:
        """Retrieve a shard (legacy URL pattern, defaults to chunk 0)"""
        client_ip = request.remote
        content_hash = request.match_info['content_hash']
        shard_index = request.match_info['shard_index']
        
        return await self._retrieve_shard_impl(client_ip, content_hash, '0', shard_index, request)
    
    async def _retrieve_shard_impl(self, client_ip: str, content_hash: str, chunk_index: str, shard_index: str, request: web.Request) -> web.Response:
        """Implementation for retrieving shards"""
        range_header = request.headers.get('Range')
        
        logger.info(f"[DOWNLOAD] Request from {client_ip}")
        logger.info(f"[DOWNLOAD] Hash: {content_hash[:16]}... Chunk: {chunk_index}, Shard: {shard_index}")
        if range_header:
            logger.info(f"[DOWNLOAD] Range: {range_header}")
        
        start_time = datetime.now()
        
        try:
            shard_path = self.storage_path / content_hash / chunk_index / f"{shard_index}.shard"
            
            if not shard_path.exists():
                logger.warning(f"[DOWNLOAD] ✗ Not found: {shard_path}")
                return web.json_response({'error': 'Shard not found'}, status=404)
            
            async with aiofiles.open(shard_path, 'rb') as f:
                data = await f.read()
            
            # Handle range requests
            if range_header:
                range_spec = range_header.replace('bytes=', '').split('-')
                start = int(range_spec[0]) if range_spec[0] else 0
                end = int(range_spec[1]) if range_spec[1] else len(data) - 1
                
                start = max(0, start)
                end = min(len(data) - 1, end)
                chunk = data[start:end + 1]
                
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"[DOWNLOAD] ✓ Partial: {len(chunk)} bytes ({start}-{end}) in {elapsed:.3f}s")
                
                self.stats['downloads'] += 1
                self.stats['total_bytes_sent'] += len(chunk)
                
                return web.Response(
                    body=chunk,
                    status=206,
                    content_type='application/octet-stream',
                    headers={
                        'Content-Range': f'bytes {start}-{end}/{len(data)}',
                        'Content-Length': str(len(chunk)),
                        'Accept-Ranges': 'bytes'
                    }
                )
            else:
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"[DOWNLOAD] ✓ Full: {len(data)} bytes in {elapsed:.3f}s")
                
                self.stats['downloads'] += 1
                self.stats['total_bytes_sent'] += len(data)
                
                return web.Response(
                    body=data,
                    content_type='application/octet-stream',
                    headers={
                        'Content-Length': str(len(data)),
                        'Accept-Ranges': 'bytes'
                    }
                )
            
        except Exception as e:
            self.stats['errors'] += 1
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"[DOWNLOAD] ✗ Failed: {e} ({elapsed:.3f}s)")
            return web.json_response({'error': str(e)}, status=500)
    
    #  DELETE ENDPOINTS 
    
    async def delete_shard(self, request: web.Request) -> web.Response:
        """Delete a specific shard"""
        client_ip = request.remote
        content_hash = request.match_info['content_hash']
        chunk_index = request.match_info['chunk_index']
        shard_index = request.match_info['shard_index']
        
        logger.info(f"[DELETE] Request from {client_ip}")
        logger.info(f"[DELETE] Hash: {content_hash[:16]}... Chunk: {chunk_index}, Shard: {shard_index}")
        
        try:
            shard_path = self.storage_path / content_hash / chunk_index / f"{shard_index}.shard"
            metadata_path = self.storage_path / content_hash / chunk_index / f"{shard_index}.meta"
            
            deleted = False
            if shard_path.exists():
                shard_path.unlink()
                logger.info(f"[DELETE] ✓ Deleted shard file")
                deleted = True
            
            if metadata_path.exists():
                metadata_path.unlink()
                logger.info(f"[DELETE] ✓ Deleted metadata file")
                deleted = True
            
            if deleted:
                self.stats['deletes'] += 1
            
            return web.json_response({'status': 'deleted', 'deleted': deleted})
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"[DELETE] ✗ Failed: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def delete_all_shards(self, request: web.Request) -> web.Response:
        """Delete all shards for a content hash"""
        content_hash = request.match_info['content_hash']
        
        logger.info(f"[DELETE] Deleting all shards for {content_hash[:16]}...")
        
        try:
            content_dir = self.storage_path / content_hash
            deleted_count = 0
            
            if content_dir.exists():
                for shard_file in content_dir.rglob('*.shard'):
                    shard_file.unlink()
                    deleted_count += 1
                
                # Remove empty directories
                for chunk_dir in content_dir.iterdir():
                    if chunk_dir.is_dir() and not any(chunk_dir.iterdir()):
                        chunk_dir.rmdir()
                
                if not any(content_dir.iterdir()):
                    content_dir.rmdir()
            
            logger.info(f"[DELETE] ✓ Deleted {deleted_count} shards")
            self.stats['deletes'] += deleted_count
            
            return web.json_response({
                'status': 'deleted',
                'content_hash': content_hash,
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"[DELETE] ✗ Failed: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    #  MANAGEMENT ENDPOINTS 
    
    async def health_check(self, request: web.Request) -> web.Response:
        """Health check with system metrics"""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(str(self.storage_path.absolute()))
            
            return web.json_response({
                'status': 'healthy',
                'node_id': self.node_id,
                'port': self.port,
                'timestamp': datetime.now().isoformat(),
                'system': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_available_mb': round(memory.available / 1024 / 1024, 2),
                    'disk_percent': disk.percent,
                    'disk_free_gb': round(disk.free / 1024 / 1024 / 1024, 2)
                }
            })
        except Exception as e:
            return web.json_response({
                'status': 'degraded',
                'node_id': self.node_id,
                'error': str(e)
            }, status=500)
    
    async def get_stats(self, request: web.Request) -> web.Response:
        """Get storage statistics"""
        total_size = 0
        shard_count = 0
        chunk_count = 0
        
        if self.storage_path.exists():
            for shard_file in self.storage_path.rglob('*.shard'):
                total_size += shard_file.stat().st_size
                shard_count += 1
            
            chunk_count = len(list(self.storage_path.rglob('*/')))
        
        uptime = (datetime.now() - datetime.fromisoformat(self.stats['started_at'])).total_seconds()
        
        return web.json_response({
            'node_id': self.node_id,
            'port': self.port,
            'shard_count': shard_count,
            'chunk_count': chunk_count,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / 1024 / 1024, 2),
            'storage_path': str(self.storage_path.absolute()),
            'uptime_seconds': round(uptime, 2),
            'operations': {
                'uploads': self.stats['uploads'],
                'downloads': self.stats['downloads'],
                'deletes': self.stats['deletes'],
                'errors': self.stats['errors']
            },
            'bandwidth': {
                'bytes_received': self.stats['total_bytes_received'],
                'bytes_sent': self.stats['total_bytes_sent'],
                'mb_received': round(self.stats['total_bytes_received'] / 1024 / 1024, 2),
                'mb_sent': round(self.stats['total_bytes_sent'] / 1024 / 1024, 2)
            }
        })
    
    async def get_metrics(self, request: web.Request) -> web.Response:
        """Prometheus-style metrics"""
        metrics = [
            f'aether_node_info{{node_id="{self.node_id}",port="{self.port}"}} 1',
            f'aether_node_shards_total {self._count_shards()}',
            f'aether_node_storage_bytes {self._get_storage_size()}',
            f'aether_node_uploads_total {self.stats["uploads"]}',
            f'aether_node_downloads_total {self.stats["downloads"]}',
            f'aether_node_deletes_total {self.stats["deletes"]}',
            f'aether_node_errors_total {self.stats["errors"]}',
            f'aether_node_bytes_received_total {self.stats["total_bytes_received"]}',
            f'aether_node_bytes_sent_total {self.stats["total_bytes_sent"]}'
        ]
        
        return web.Response(text='\n'.join(metrics), content_type='text/plain')
    
    async def list_shards(self, request: web.Request) -> web.Response:
        """List all shards stored on this node"""
        shards = []
        
        if self.storage_path.exists():
            for shard_file in self.storage_path.rglob('*.shard'):
                rel_path = shard_file.relative_to(self.storage_path)
                parts = rel_path.parts
                
                if len(parts) >= 3:
                    content_hash = parts[0]
                    chunk_index = parts[1]
                    shard_index = parts[2].replace('.shard', '')
                    
                    shards.append({
                        'content_hash': content_hash,
                        'chunk_index': chunk_index,
                        'shard_index': shard_index,
                        'size': shard_file.stat().st_size,
                        'path': str(shard_file)
                    })
        
        return web.json_response({
            'node_id': self.node_id,
            'total_shards': len(shards),
            'shards': shards[:100]  # Limit to first 100
        })
    
    async def gossip_handler(self, request: web.Request) -> web.Response:
        """Handle gossip messages from other nodes"""
        try:
            data = await request.json()
            
            node_id = data.get('node_id')
            action = data.get('action', 'gossip')
            peers = data.get('peers', [])
            
            logger.info(f"[GOSSIP] From {node_id} (action: {action}, peers: {len(peers)})")
            
            # Return peer list excluding self and requesting node
            all_peers = [p for p in peers if p != self.node_id and p != node_id]
            
            logger.info(f"[GOSSIP] Returning {len(all_peers)} peers")
            
            return web.json_response({
                'status': 'received',
                'node_id': self.node_id,
                'peers': all_peers,
                'version': 1
            })
            
        except Exception as e:
            logger.error(f"[GOSSIP] Error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    #  HELPER METHODS 
    
    def _count_shards(self) -> int:
        """Count total shards"""
        if not self.storage_path.exists():
            return 0
        return sum(1 for _ in self.storage_path.rglob('*.shard'))
    
    def _get_storage_size(self) -> int:
        """Get total storage size in bytes"""
        if not self.storage_path.exists():
            return 0
        return sum(f.stat().st_size for f in self.storage_path.rglob('*.shard'))
    
    async def start(self):
        """Start the storage node server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        
        logger.info("=" * 70)
        logger.info(f"Storage node {self.node_id} listening on port {self.port}")
        logger.info(f"Storage path: {self.storage_path.absolute()}")
        logger.info(f"Endpoints:")
        logger.info(f"  PUT    /shard/{{hash}}/{{chunk}}/{{shard}}  - Store shard")
        logger.info(f"  GET    /shard/{{hash}}/{{chunk}}/{{shard}}  - Retrieve shard")
        logger.info(f"  DELETE /shard/{{hash}}/{{chunk}}/{{shard}}  - Delete shard")
        logger.info(f"  GET    /health                            - Health check")
        logger.info(f"  GET    /stats                             - Storage stats")
        logger.info(f"  GET    /metrics                           - Prometheus metrics")
        logger.info(f"  GET    /shards                            - List shards")
        logger.info(f"  POST   /gossip                            - Gossip protocol")
        logger.info("=" * 70)
        
        while True:
            await asyncio.sleep(3600)


if __name__ == '__main__':
    import sys
    node_id = sys.argv[1] if len(sys.argv) > 1 else 'node-1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
    
    server = StorageNodeServer(node_id, port)
    asyncio.run(server.start())