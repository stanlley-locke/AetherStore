from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from apps.storage.models import StorageObject, StorageNode
from apps.storage.engine import get_erasure_engine
from apps.p2p.ring import get_hash_ring
import httpx
import logging

logger = logging.getLogger(__name__)

@shared_task
def audit_storage_health():
    """Periodic audit of shard integrity"""
    logger.info("Starting storage audit...")
    
    # Get recent objects
    recent_objects = StorageObject.objects.filter(
        updated_at__gte=timezone.now() - timedelta(hours=1),
        is_deleted=False
    )[:100]
    
    issues = 0
    
    for obj in recent_objects:
        try:
            # Check each shard
            for node_id, shard_index in obj.shard_map.items():
                try:
                    node = StorageNode.objects.get(node_id=node_id)
                    
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.head(
                            f"{node.endpoint}/shard/{obj.content_hash}/{shard_index}"
                        )
                        
                        if resp.status_code != 200:
                            logger.warning(f"Shard {shard_index} unavailable on {node_id}")
                            issues += 1
                            
                except StorageNode.DoesNotExist:
                    logger.warning(f"Node {node_id} missing")
                    issues += 1
                    
        except Exception as e:
            logger.error(f"Audit error for {obj.id}: {e}")
    
    if issues > 0:
        logger.warning(f"Audit found {issues} issues")
    
    return {'issues': issues}

@shared_task(bind=True, max_retries=3)
def repair_object(self, object_id):
    """Repair object with missing/corrupted shards"""
    try:
        obj = StorageObject.objects.get(id=object_id, is_deleted=False)
    except StorageObject.DoesNotExist:
        logger.error(f"Object {object_id} not found")
        return
    
    logger.info(f"Repairing object {object_id}")
    
    engine = get_erasure_engine()
    ring = get_hash_ring()
    
    # Fetch existing shards
    existing_shards = [None] * engine.total_shards
    valid_count = 0
    
    with httpx.Client(timeout=10.0) as client:
        for node_id, shard_index in obj.shard_map.items():
            try:
                node = StorageNode.objects.get(node_id=node_id, is_active=True)
                resp = client.get(f"{node.endpoint}/shard/{obj.content_hash}/{shard_index}")
                
                if resp.status_code == 200:
                    existing_shards[shard_index] = resp.content
                    valid_count += 1
            except:
                continue
    
    # Check if recoverable
    if valid_count < engine.data_shards:
        logger.error(f"Cannot repair: only {valid_count} shards")
        raise self.retry(countdown=300)
    
    # Decode and re-encode
    try:
        data = engine.decode(existing_shards)
        new_shards = engine.encode(data)
    except Exception as e:
        logger.error(f"Decode failed: {e}")
        raise self.retry(countdown=300)
    
    # Find new nodes
    target_nodes = ring.get_all_nodes_for_object(obj.content_hash, len(new_shards))
    
    # Distribute repaired shards
    new_shard_map = {}
    
    with httpx.Client(timeout=10.0) as client:
        for shard_index, shard_data in enumerate(new_shards):
            nodes = target_nodes.get(shard_index, [])
            
            for node_id, endpoint in nodes:
                try:
                    resp = client.put(
                        f"{endpoint}/shard/{obj.content_hash}/{shard_index}",
                        content=shard_data
                    )
                    
                    if resp.status_code == 200:
                        new_shard_map[node_id] = shard_index
                        break
                except:
                    continue
    
    # Update metadata
    if len(new_shard_map) >= engine.data_shards:
        obj.shard_map = new_shard_map
        obj.updated_at = timezone.now()
        obj.save()
        logger.info(f"Repair complete for {object_id}")
    else:
        logger.error(f"Repair incomplete: {len(new_shard_map)} shards")
        raise self.retry(countdown=300)

@shared_task
def node_heartbeat():
    """Update heartbeat and detect dead nodes"""
    from django.conf import settings
    
    # Update current node
    node_id = getattr(settings, 'NODE_ID', None)
    if node_id:
        StorageNode.objects.filter(node_id=node_id).update(
            last_heartbeat=timezone.now()
        )
    
    # Detect dead nodes
    dead_nodes = StorageNode.objects.filter(
        is_active=True,
        last_heartbeat__lt=timezone.now() - timedelta(minutes=5)
    )
    
    for node in dead_nodes:
        logger.warning(f"Node {node.node_id} marked dead")
        node.is_active = False
        node.save()
        
        # Invalidate hash ring
        ring = get_hash_ring()
        ring.invalidate()
        
        # Trigger repair
        affected = StorageObject.objects.filter(
            shard_map__has_key=node.node_id,
            is_deleted=False
        )
        
        for obj in affected:
            repair_object.delay(str(obj.id))
