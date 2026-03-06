"""
Download Service with Range Request Support
Streaming downloads without loading entire file into memory
"""

import asyncio
import aiofiles
import httpx
from typing import Dict, List, Optional, AsyncGenerator
from django.http import StreamingHttpResponse
from apps.storage.models import StorageObject, StorageNode, AccessLog
from apps.storage.engine import get_erasure_engine
from apps.p2p.ring import get_hash_ring
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class DownloadService:
    """Handle file downloads with streaming and range support"""
    
    @classmethod
    async def download_file(
        cls,
        object_id: str,
        user_did: str,
        range_start: Optional[int] = None,
        range_end: Optional[int] = None
    ) -> StreamingHttpResponse:
        """
        Download file with optional range support
        """
        # 1. Get object metadata
        try:
            obj = StorageObject.objects.get(id=object_id, is_deleted=False)
        except StorageObject.DoesNotExist:
            raise Exception('Object not found')
        
        # 2. Fetch and decode shards
        engine = get_erasure_engine()
        
        if range_start is not None and range_end is not None:
            # Range request - optimize shard fetching
            shards = await cls._fetch_range_shards(obj, range_start, range_end)
            full_data = engine.decode(shards)
            
            # Slice to requested range
            chunk = full_data[range_start:range_end + 1]
            
            response = StreamingHttpResponse(
                cls._bytes_iterator(chunk),
                content_type=obj.mime_type,
                status=206
            )
            response['Content-Range'] = f'bytes {range_start}-{range_end}/{obj.size}'
            response['Content-Length'] = str(len(chunk))
        else:
            # Full download
            shards = await cls._fetch_all_shards(obj)
            
            # Stream decode
            response = StreamingHttpResponse(
                cls._stream_decode(shards, engine),
                content_type=obj.mime_type
            )
            response['Content-Length'] = str(obj.size)
        
        # 3. Set headers
        response['Accept-Ranges'] = 'bytes'
        response['Content-Disposition'] = f'attachment; filename="{object_id}"'
        
        # 4. Log access
        AccessLog.objects.create(
            object=obj,
            user_did=user_did,
            action='download',
            bytes_transferred=range_end - range_start + 1 if range_start is not None else obj.size,
            status_code=response.status_code
        )
        
        return response
    
    @classmethod
    async def _fetch_all_shards(cls, obj: StorageObject) -> List[Optional[bytes]]:
        """Fetch all shards for object"""
        engine = get_erasure_engine()
        shards = [None] * engine.total_shards
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = []
            
            for node_id, shard_index in obj.shard_map.items():
                try:
                    node = StorageNode.objects.get(node_id=node_id, is_active=True)
                    task = cls._fetch_shard(client, node.endpoint, obj.content_hash, shard_index)
                    tasks.append((shard_index, task))
                except StorageNode.DoesNotExist:
                    continue
            
            for shard_index, task in tasks:
                try:
                    shard_data = await task
                    if shard_data:
                        shards[shard_index] = shard_data
                except Exception as e:
                    logger.error(f"Shard {shard_index} fetch failed: {e}")
        
        return shards
    
    @classmethod
    async def _fetch_range_shards(
        cls,
        obj: StorageObject,
        range_start: int,
        range_end: int
    ) -> List[Optional[bytes]]:
        """Fetch only shards needed for byte range"""
        engine = get_erasure_engine()
        
        # Determine which shards are needed
        needed_shards = engine.get_byte_range_shards(range_start, range_end)
        
        shards = [None] * engine.total_shards
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for node_id, shard_index in obj.shard_map.items():
                if shard_index in needed_shards:
                    try:
                        node = StorageNode.objects.get(node_id=node_id, is_active=True)
                        shard_data = await cls._fetch_shard(
                            client,
                            node.endpoint,
                            obj.content_hash,
                            shard_index
                        )
                        shards[shard_index] = shard_data
                    except Exception as e:
                        logger.error(f"Shard {shard_index} fetch failed: {e}")
        
        return shards
    
    @classmethod
    async def _fetch_shard(
        cls,
        client: httpx.AsyncClient,
        endpoint: str,
        content_hash: str,
        shard_index: int
    ) -> Optional[bytes]:
        """Fetch single shard from node"""
        try:
            response = await client.get(
                f"{endpoint}/shard/{content_hash}/{shard_index}",
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.content
            else:
                return None
        
        except Exception as e:
            logger.error(f"Shard fetch from {endpoint} failed: {e}")
            return None
    
    @classmethod
    async def _stream_decode(
        cls,
        shards: List[Optional[bytes]],
        engine
    ) -> AsyncGenerator[bytes, None]:
        """Stream decoded data in chunks"""
        # Decode all shards (need all for Reed-Solomon)
        data = engine.decode(shards)
        
        # Yield in chunks
        chunk_size = 8192  # 8KB
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]
    
    @classmethod
    def _bytes_iterator(cls, data: bytes) -> AsyncGenerator[bytes, None]:
        """Convert bytes to async iterator"""
        async def iterator():
            yield data
        return iterator()
    
    @classmethod
    async def delete_object(cls, object_id: str, user_did: str) -> Dict:
        """Delete object and signal nodes to purge shards"""
        try:
            obj = StorageObject.objects.get(id=object_id)
            
            # Verify ownership
            if obj.owner_did != user_did:
                return {'error': 'Access denied', 'status': 'forbidden'}
            
            # Signal nodes to delete shards
            await cls._signal_node_deletion(obj)
            
            # Mark as deleted
            obj.is_deleted = True
            obj.save()
            
            # Log
            AccessLog.objects.create(
                object=obj,
                user_did=user_did,
                action='delete',
                status_code=200
            )
            
            return {'status': 'deleted', 'object_id': str(obj.id)}
        
        except StorageObject.DoesNotExist:
            return {'error': 'Object not found', 'status': 'not_found'}
    
    @classmethod
    async def _signal_node_deletion(cls, obj: StorageObject):
        """Signal storage nodes to delete shards"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = []
            
            for node_id, shard_index in obj.shard_map.items():
                try:
                    node = StorageNode.objects.get(node_id=node_id)
                    task = client.delete(
                        f"{node.endpoint}/shard/{obj.content_hash}/{shard_index}"
                    )
                    tasks.append(task)
                except:
                    continue
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
