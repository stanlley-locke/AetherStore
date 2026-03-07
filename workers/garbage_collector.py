from celery import shared_task
import logging
import httpx
from django.db import transaction

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_garbage_collection(self, object_id):
    """
    Background worker to physically delete orphaned shards from P2P nodes
    when an object is soft-deleted.
    """
    try:
        from apps.storage.models import EncryptedObject, StorageNode
        from apps.core.dht import dht_service
        
        logger.info(f"Starting garbage collection for object {object_id}")
        
        # 1. Retrieve the deleted object
        try:
            obj = EncryptedObject.objects.get(id=object_id, is_deleted=True)
        except EncryptedObject.DoesNotExist:
            logger.warning(f"Object {object_id} not found or not marked for deletion.")
            return {'status': 'skipped', 'reason': 'not_found'}
            
        from apps.storage.models import ObjectVersion
        versions = ObjectVersion.objects.filter(object=obj)
        
        # Collect all root hashes and shard maps across the object and its versions
        all_root_hashes = {obj.root_hash}
        for v in versions:
            all_root_hashes.add(v.root_hash)
            
        # Prevent deletion if ANY other active object shares these root hashes
        active_copies = EncryptedObject.objects.filter(root_hash__in=all_root_hashes, is_deleted=False).exists()
        if active_copies:
            logger.info(f"Skipping physical deletion for object {object_id}: Active copies share roots.")
            return {'status': 'skipped', 'reason': 'active_copies_exist'}
            
        # Build union of all shards across all versions
        # Key: (root_hash, chunk_index, shard_index) -> node_id
        flattened_shards = {}
        
        def add_shards(root_val, map_val):
            for shard_key, node_id in map_val.items():
                chunk_index, shard_index = shard_key.split(':')
                flattened_shards[(root_val, chunk_index, shard_index)] = node_id
                
        add_shards(obj.root_hash, obj.shard_map)
        for v in versions:
            add_shards(v.root_hash, v.shard_map)
            
        # 2. Map node_ids to endpoints
        unique_node_ids = set(flattened_shards.values())
        nodes_info = StorageNode.objects.filter(node_id__in=unique_node_ids)
        endpoint_map = {node.node_id: node.endpoint for node in nodes_info}
        
        dht = dht_service.get_node()
        deleted_count = 0
        failed_count = 0
        
        # 3. Fire DELETE requests to nodes
        with httpx.Client(timeout=10.0) as client:
            for (r_hash, chunk_index, shard_index), node_id in flattened_shards.items():
                endpoint = endpoint_map.get(node_id)
                
                if not endpoint:
                    logger.warning(f"Node {node_id} endpoint not found for shard {chunk_index}:{shard_index}")
                    failed_count += 1
                    continue
                    
                delete_url = f"{endpoint}/shard/{r_hash}/{chunk_index}/{shard_index}"
                
                try:
                    response = client.delete(delete_url)
                    if response.status_code in (200, 204, 404):
                        deleted_count += 1
                        dht.delete_shard_location(r_hash, int(chunk_index), int(shard_index), node_id)
                    else:
                        logger.warning(f"Failed to delete {chunk_index}:{shard_index} from {node_id}: HTTP {response.status_code}")
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error connecting to node {node_id}: {e}")
                    failed_count += 1
                    
        logger.info(f"Garbage collection completed for {object_id}: {deleted_count} deleted, {failed_count} failures.")
        
        # Optionally hard delete from db if completely successful
        if failed_count == 0:
            logger.info(f"Purging database record for {object_id}")
            obj.delete()
            return {'status': 'success', 'deleted': deleted_count}
        else:
            logger.warning(f"Partial deletion for {object_id}, keeping DB record for future retry.")
            # Could raise self.retry() here, but for now we'll just return partial success
            return {'status': 'partial', 'deleted': deleted_count, 'failed': failed_count}
            
    except Exception as exc:
        logger.error(f"Garbage collection failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)

@shared_task
def sweep_deleted_objects():
    """
    Periodically sweeps for objects that have been soft-deleted for more than 7 days
    and ensures their physical shards are purged network-wide.
    """
    from apps.storage.models import EncryptedObject
    from django.utils import timezone
    from datetime import timedelta
    
    threshold = timezone.now() - timedelta(days=7)
    
    # Find objects marked deleted older than 7 days
    orphans = EncryptedObject.objects.filter(
        is_deleted=True,
        deleted_at__lte=threshold
    )
    
    count = orphans.count()
    if count > 0:
        logger.info(f"Sweeping {count} soft-deleted objects older than 7 days...")
        for obj in orphans:
            process_garbage_collection.delay(str(obj.id))
            
    return f"Triggered sweeping for {count} objects."
