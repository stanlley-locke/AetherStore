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
            
        root_hash = obj.root_hash
        shard_map = obj.shard_map
        
        # Prevent deletion if another active object shares the same Merkle root (Basic deduplication protection)
        active_copies = EncryptedObject.objects.filter(root_hash=root_hash, is_deleted=False).exists()
        if active_copies:
            logger.info(f"Skipping physical deletion for {root_hash}: Active copies still exist.")
            return {'status': 'skipped', 'reason': 'active_copies_exist'}
            
        # 2. Map node_ids to endpoints
        unique_node_ids = set(shard_map.values())
        nodes_info = StorageNode.objects.filter(node_id__in=unique_node_ids)
        endpoint_map = {node.node_id: node.endpoint for node in nodes_info}
        
        dht = dht_service.get_node()
        deleted_count = 0
        failed_count = 0
        
        # 3. Fire DELETE requests to nodes
        with httpx.Client(timeout=10.0) as client:
            for shard_key, node_id in shard_map.items():
                chunk_index, shard_index = shard_key.split(':')
                endpoint = endpoint_map.get(node_id)
                
                if not endpoint:
                    logger.warning(f"Node {node_id} endpoint not found for shard {shard_key}")
                    failed_count += 1
                    continue
                    
                delete_url = f"{endpoint}/shard/{root_hash}/{chunk_index}/{shard_index}"
                
                try:
                    response = client.delete(delete_url)
                    if response.status_code in (200, 204, 404):
                        # 404 means already deleted, which is fine
                        deleted_count += 1
                        # Remove from DHT
                        dht.delete_shard_location(root_hash, int(chunk_index), int(shard_index), node_id)
                    else:
                        logger.warning(f"Failed to delete {shard_key} from {node_id}: HTTP {response.status_code}")
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
