"""
P2P Storage Node Server with Comprehensive Logging
Handles shard storage and retrieval with async I/O
"""

import asyncio
import aiofiles
from aiohttp import web
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class StorageNodeServer:
    """Async HTTP server for shard storage operations with comprehensive logging"""
    
    def __init__(self, node_id: str, port: int, storage_path: str = './data/shards'):
        self.node_id = node_id
        self.port = port
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.app = web.Application()
        self._setup_routes()
        
        logger.info(f"Initializing storage node {node_id} on port {port}")
        logger.info(f"Storage path: {self.storage_path.absolute()}")
    
    def _setup_routes(self):
        self.app.router.add_put('/shard/{content_hash}/{shard_index}', self.store_shard)
        self.app.router.add_get('/shard/{content_hash}/{shard_index}', self.retrieve_shard)
        self.app.router.add_delete('/shard/{content_hash}/{shard_index}', self.delete_shard)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/stats', self.get_stats)
        self.app.router.add_post('/gossip', self.gossip_handler)
    
    async def store_shard(self, request: web.Request) -> web.Response:
        """Store a shard with async I/O and comprehensive logging"""
        client_ip = request.remote
        content_hash = request.match_info['content_hash']
        shard_index = request.match_info['shard_index']
        
        logger.info(f"[UPLOAD] Receiving shard from {client_ip}")
        logger.info(f"[UPLOAD] Content hash: {content_hash[:16]}...")
        logger.info(f"[UPLOAD] Shard index: {shard_index}")
        
        start_time = datetime.now()
        
        try:
            data = await request.read()
            actual_hash = hashlib.sha256(data).hexdigest()
            
            logger.info(f"[UPLOAD] Received {len(data)} bytes")
            logger.info(f"[UPLOAD] Computed hash: {actual_hash[:16]}...")
            
            shard_dir = self.storage_path / content_hash
            shard_dir.mkdir(parents=True, exist_ok=True)
            shard_path = shard_dir / f"{shard_index}.shard"
            
            async with aiofiles.open(shard_path, 'wb') as f:
                await f.write(data)
            
            # Store metadata
            metadata = {
                'content_hash': content_hash,
                'shard_index': int(shard_index),
                'size': len(data),
                'hash': actual_hash,
                'node_id': self.node_id,
                'stored_at': datetime.now().isoformat(),
                'received_from': client_ip
            }
            
            metadata_path = shard_dir / f"{shard_index}.meta"
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(json.dumps(metadata, indent=2))
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"[UPLOAD]  Shard stored successfully in {elapsed:.3f}s")
            logger.info(f"[UPLOAD] Path: {shard_path}")
            
            return web.json_response({
                'status': 'stored',
                'content_hash': content_hash,
                'shard_index': shard_index,
                'size': len(data),
                'node_id': self.node_id
            })
            
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"[UPLOAD]  Failed to store shard: {e} (took {elapsed:.3f}s)")
            return web.json_response({'error': str(e)}, status=500)
    
    async def retrieve_shard(self, request: web.Request) -> web.Response:
        """Retrieve a shard with async I/O and comprehensive logging"""
        client_ip = request.remote
        content_hash = request.match_info['content_hash']
        shard_index = request.match_info['shard_index']
        range_header = request.headers.get('Range')
        
        logger.info(f"[DOWNLOAD] Shard request from {client_ip}")
        logger.info(f"[DOWNLOAD] Content hash: {content_hash[:16]}...")
        logger.info(f"[DOWNLOAD] Shard index: {shard_index}")
        if range_header:
            logger.info(f"[DOWNLOAD] Range request: {range_header}")
        
        start_time = datetime.now()
        
        try:
            shard_path = self.storage_path / content_hash / f"{shard_index}.shard"
            
            if not shard_path.exists():
                logger.warning(f"[DOWNLOAD]  Shard not found: {shard_path}")
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
                logger.info(f"[DOWNLOAD]  Serving partial content ({len(chunk)} bytes) in {elapsed:.3f}s")
                
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
                logger.info(f"[DOWNLOAD]  Serving full shard ({len(data)} bytes) in {elapsed:.3f}s")
                
                return web.Response(
                    body=data,
                    content_type='application/octet-stream',
                    headers={
                        'Content-Length': str(len(data)),
                        'Accept-Ranges': 'bytes'
                    }
                )
            
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"[DOWNLOAD]  Failed to retrieve shard: {e} (took {elapsed:.3f}s)")
            return web.json_response({'error': str(e)}, status=500)
    
    async def delete_shard(self, request: web.Request) -> web.Response:
        """Delete a shard with logging"""
        client_ip = request.remote
        content_hash = request.match_info['content_hash']
        shard_index = request.match_info['shard_index']
        
        logger.info(f"[DELETE] Delete request from {client_ip}")
        logger.info(f"[DELETE] Content hash: {content_hash[:16]}...")
        logger.info(f"[DELETE] Shard index: {shard_index}")
        
        try:
            shard_path = self.storage_path / content_hash / f"{shard_index}.shard"
            metadata_path = self.storage_path / content_hash / f"{shard_index}.meta"
            
            if shard_path.exists():
                shard_path.unlink()
                logger.info(f"[DELETE]  Deleted shard file")
            
            if metadata_path.exists():
                metadata_path.unlink()
                logger.info(f"[DELETE]  Deleted metadata file")
            
            return web.json_response({'status': 'deleted'})
            
        except Exception as e:
            logger.error(f"[DELETE]  Failed to delete shard: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint with logging"""
        client_ip = request.remote
        logger.debug(f"[HEALTH] Health check from {client_ip}")
        
        return web.json_response({
            'status': 'healthy',
            'node_id': self.node_id,
            'port': self.port,
            'timestamp': datetime.now().isoformat()
        })
    
    async def get_stats(self, request: web.Request) -> web.Response:
        """Get storage statistics with logging"""
        client_ip = request.remote
        logger.debug(f"[STATS] Stats request from {client_ip}")
        
        total_size = 0
        shard_count = 0
        
        if self.storage_path.exists():
            for shard_file in self.storage_path.rglob('*.shard'):
                total_size += shard_file.stat().st_size
                shard_count += 1
        
        logger.info(f"[STATS] Node stats: {shard_count} shards, {total_size} bytes")
        
        return web.json_response({
            'node_id': self.node_id,
            'shard_count': shard_count,
            'total_size_bytes': total_size,
            'storage_path': str(self.storage_path.absolute())
        })
    
    async def gossip_handler(self, request: web.Request) -> web.Response:
        """Handle incoming gossip messages with logging"""
        client_ip = request.remote
        
        try:
            data = await request.json()
            
            node_id = data.get('node_id')
            action = data.get('action', 'gossip')
            peers = data.get('peers', [])
            
            logger.info(f"[GOSSIP] Received from {node_id} ({client_ip})")
            logger.info(f"[GOSSIP] Action: {action}")
            logger.info(f"[GOSSIP] Known peers: {len(peers)}")
            
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
            logger.error(f"[GOSSIP] Error handling gossip: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def start(self):
        """Start the storage node server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        
        logger.info("=" * 6)
        logger.info(f"Storage node {self.node_id} listening on port {self.port}")
        logger.info(f"Storage path: {self.storage_path.absolute()}")
        logger.info("=" * 6)
        
        while True:
            await asyncio.sleep(3600)


if __name__ == '__main__':
    import sys
    node_id = sys.argv[1] if len(sys.argv) > 1 else 'node-1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
    
    server = StorageNodeServer(node_id, port)
    asyncio.run(server.start())
