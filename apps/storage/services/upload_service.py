"""
Upload Service with Deduplication and Shard Distribution
"""

import asyncio
import aiofiles
import httpx
from typing import Dict, List, Optional
from django.db import transaction
from django.core.cache import cache
from apps.storage.models import StorageObject, Bucket, StorageQuota
from apps.storage.engine import get_erasure_engine
from apps.p2p.ring import get_hash_ring
import hashlib
import logging

logger = logging.getLogger(__name__)

class UploadService:
    """Handle file uploads with deduplication and shard distribution"""
    
    DEDUP_CACHE_TTL = 3600  # 1 hour
    
    @classmethod
    async def upload_file(
        cls,
        file_data: bytes,
        bucket_name: str,
        owner_did: str,
        mime_type: str = 'application/octet-stream'
    ) -> Dict:
        """
        Upload file with deduplication and erasure coding
        """
        engine = get_erasure_engine()
        ring = get_hash_ring()
        
        # 1. Compute content hash for deduplication
        content_hash = engine.compute_content_hash(file_data)
        
        # 2. Check for existing object (deduplication)
        existing = await cls._check_deduplication(content_hash)
        if existing:
            logger.info(f"Deduplication hit for {content_hash[:16]}")
            return {
                'status': 'deduplicated',
                'object_id': str(existing.id),
                'content_hash': content_hash
            }
        
        # 3. Encode with erasure coding
        shards = engine.encode(file_data)
        
        # 4. Get target nodes from hash ring
        total_shards = len(shards)
        shard_map = ring.get_all_nodes_for_object(content_hash, total_shards)
        
        # 5. Distribute shards to nodes
        distribution_result = await cls._distribute_shards(content_hash, shards, shard_map)
        
        if not distribution_result['success']:
            raise Exception(f"Shard distribution failed: {distribution_result['error']}")
        
        # 6. Save metadata (atomic transaction)
        with transaction.atomic():
            # Get or create bucket
            bucket, _ = Bucket.objects.get_or_create(
                name=bucket_name,
                defaults={'owner_did': owner_did}
            )
            
            # Create object record
            obj = StorageObject.objects.create(
                content_hash=content_hash,
                bucket=bucket,
                mime_type=mime_type,
                size=len(file_data),
                owner_did=owner_did,
                shard_map=distribution_result['shard_map'],
                shard_hashes=distribution_result['shard_hashes']
            )
            
            # Update quota
            cls._update_quota(owner_did, len(file_data))
        
        # 7. Cache for deduplication
        cache.set(f'dedup:{content_hash}', str(obj.id), cls.DEDUP_CACHE_TTL)
        
        logger.info(f"Upload complete: {content_hash[:16]} ({len(file_data)} bytes)")
        
        return {
            'status': 'uploaded',
            'object_id': str(obj.id),
            'content_hash': content_hash,
            'size': len(file_data),
            'shards': total_shards
        }
    
    @classmethod
    async def _check_deduplication(cls, content_hash: str) -> Optional[StorageObject]:
        """Check if object already exists"""
        # Check cache first
        cached_id = cache.get(f'dedup:{content_hash}')
        if cached_id:
            try:
                return StorageObject.objects.get(id=cached_id, is_deleted=False)
            except StorageObject.DoesNotExist:
                cache.delete(f'dedup:{content_hash}')
        
        # Check database
        try:
            return StorageObject.objects.get(
                content_hash=content_hash,
                is_deleted=False
            )
        except StorageObject.DoesNotExist:
            return None
    
    @classmethod
    async def _distribute_shards(
        cls,
        content_hash: str,
        shards: List[bytes],
        shard_map: Dict[int, List[tuple]]
    ) -> Dict:
        """Distribute shards to storage nodes"""
        result_shard_map = {}
        result_shard_hashes = {}
        failed_shards = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = []
            
            for shard_index, shard_data in enumerate(shards):
                nodes = shard_map.get(shard_index, [])
                
                if not nodes:
                    failed_shards.append(shard_index)
                    continue
                
                # Try primary node first
                node_id, endpoint = nodes[0]
                
                task = cls._store_shard(
                    client,
                    node_id,
                    endpoint,
                    content_hash,
                    shard_index,
                    shard_data
                )
                tasks.append((shard_index, task))
            
            # Execute all storage tasks
            for shard_index, task in tasks:
                try:
                    success, node_id = await task
                    
                    if success:
                        result_shard_map[node_id] = shard_index
                        result_shard_hashes[shard_index] = hashlib.sha256(
                            shards[shard_index]
                        ).hexdigest()
                    else:
                        # Try backup nodes
                        for backup_node_id, backup_endpoint in shard_map[shard_index][1:]:
                            success, backup_node_id = await cls._store_shard(
                                client,
                                backup_node_id,
                                backup_endpoint,
                                content_hash,
                                shard_index,
                                shards[shard_index]
                            )
                            
                            if success:
                                result_shard_map[backup_node_id] = shard_index
                                result_shard_hashes[shard_index] = hashlib.sha256(
                                    shards[shard_index]
                                ).hexdigest()
                                break
                        else:
                            failed_shards.append(shard_index)
                
                except Exception as e:
                    logger.error(f"Shard {shard_index} storage failed: {e}")
                    failed_shards.append(shard_index)
        
        # Check if we have enough shards
        if len(failed_shards) > len(shards) // 3:  # More than 1/3 failed
            return {
                'success': False,
                'error': f'Too many shard failures: {len(failed_shards)}',
                'shard_map': result_shard_map,
                'shard_hashes': result_shard_hashes
            }
        
        return {
            'success': True,
            'shard_map': result_shard_map,
            'shard_hashes': result_shard_hashes
        }
    
    @classmethod
    async def _store_shard(
        cls,
        client: httpx.AsyncClient,
        node_id: str,
        endpoint: str,
        content_hash: str,
        shard_index: int,
        shard_data: bytes
    ) -> tuple:
        """Store single shard on node"""
        try:
            response = await client.put(
                f"{endpoint}/shard/{content_hash}/{shard_index}",
                content=shard_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                return (True, node_id)
            else:
                return (False, node_id)
        
        except Exception as e:
            logger.error(f"Node {node_id} storage failed: {e}")
            return (False, node_id)
    
    @classmethod
    def _update_quota(cls, owner_did: str, bytes_used: int):
        """Update storage quota"""
        quota, _ = StorageQuota.objects.get_or_create(
            owner_did=owner_did,
            defaults={'quota_bytes': 10737418240}  # 10GB default
        )
        
        quota.used_bytes += bytes_used
        quota.save()
