"""
Celery tasks for file upload processing
"""

from celery import shared_task
from django.db import transaction
import hashlib
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_upload(self, object_id, data_bytes, mime_type, bucket_id, owner_did):
    """
    Process file upload with erasure coding and shard distribution
    """
    try:
        from apps.storage.models import StorageObject, Bucket, StorageQuota
        from apps.storage.engine import get_erasure_engine
        from apps.p2p.ring import get_hash_ring
        import httpx
        
        logger.info(f"Processing upload for bucket {bucket_id}, size {len(data_bytes)} bytes")
        
        engine = get_erasure_engine()
        content_hash = engine.compute_content_hash(data_bytes)
        
        # Check deduplication
        if StorageObject.objects.filter(content_hash=content_hash, is_deleted=False).exists():
            logger.info(f"Deduplication hit for {content_hash[:16]}")
            existing = StorageObject.objects.get(content_hash=content_hash, is_deleted=False)
            return {
                'status': 'deduplicated',
                'object_id': str(existing.id),
                'content_hash': content_hash
            }
        
        # Encode
        logger.info(f"Encoding data into {engine.total_shards} shards...")
        shards = engine.encode(data_bytes)
        
        # Get nodes from hash ring
        ring = get_hash_ring()
        shard_map = ring.get_all_nodes_for_object(content_hash, len(shards))
        
        available_nodes = len(ring.nodes)
        logger.info(f"Hash ring has {available_nodes} nodes: {list(ring.nodes.keys())}")
        
        # Adjust minimum shards based on available nodes
        min_shards_needed = min(engine.data_shards, available_nodes)
        logger.info(f"Minimum shards needed: {min_shards_needed} (adjusted from {engine.data_shards})")
        
        # Distribute shards
        result_shard_map = {}
        
        with httpx.Client(timeout=30.0) as client:
            for shard_index, shard_data in enumerate(shards):
                nodes = shard_map.get(shard_index, [])
                
                if not nodes:
                    logger.warning(f"No nodes available for shard {shard_index}")
                    continue
                
                for node_id, endpoint in nodes:
                    try:
                        response = client.put(
                            f"{endpoint}/shard/{content_hash}/{shard_index}",
                            content=shard_data,
                            timeout=30.0
                        )
                        
                        if response.status_code == 200:
                            result_shard_map[node_id] = shard_index
                            logger.debug(f"Shard {shard_index} stored on {node_id}")
                            break
                    except Exception as e:
                        logger.warning(f"Node {node_id} failed: {e}")
                        continue
        
        # Check if we have minimum shards
        if len(result_shard_map) < min_shards_needed:
            logger.warning(f"Only {len(result_shard_map)} shards stored, need {min_shards_needed}. Retrying...")
            raise Exception(f"Only {len(result_shard_map)} shards stored, need {min_shards_needed}")
        
        # Save metadata
        with transaction.atomic():
            bucket = Bucket.objects.get(id=bucket_id)
            
            obj = StorageObject.objects.create(
                content_hash=content_hash,
                bucket=bucket,
                mime_type=mime_type,
                size=len(data_bytes),
                owner_did=owner_did,
                shard_map=result_shard_map,
            )
            
            # Update quota
            quota, _ = StorageQuota.objects.get_or_create(
                owner_did=owner_did,
                defaults={'quota_bytes': 10737418240}
            )
            quota.used_bytes += len(data_bytes)
            quota.save()
        
        logger.info(f"✅ Upload complete: {content_hash[:16]} ({len(data_bytes)} bytes, {len(result_shard_map)} shards on {len(result_shard_map)} nodes)")
        
        return {
            'status': 'success',
            'object_id': str(obj.id),
            'content_hash': content_hash,
            'size': len(data_bytes),
            'shards_stored': len(result_shard_map),
            'nodes_used': len(set(result_shard_map.keys())),
            'erasure_coding': engine.has_erasure_coding,
        }
        
    except Exception as exc:
        logger.error(f"Upload failed: {exc}")
        raise self.retry(exc=exc)
