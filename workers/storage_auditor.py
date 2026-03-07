from celery import shared_task
import logging
from apps.storage.models import StorageNode, EncryptedObject
from django.db import transaction
import httpx
import random

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def audit_nodes(self):
    """
    Periodically audit nodes by requesting random shards they claim to hold.
    If a node fails to serve the shard or times out, slash its reputation.
    """
    logger.info("Starting Storage Node reputation audit...")
    
    active_nodes = StorageNode.objects.filter(is_active=True)
    if not active_nodes.exists():
        logger.info("No active nodes to audit.")
        return {'status': 'skipped'}
        
    for node in active_nodes:
        _audit_single_node(node)
        
    return {'status': 'success'}

def _audit_single_node(node):
    """Audit a specific Node by making it prove it has a shard."""
    # Find a random object that maps to this node
    objects = EncryptedObject.objects.filter(is_deleted=False)
    
    target_shard = None
    target_obj = None
    
    # Simple search for a shard owned by this node
    for obj in objects.order_by('?')[:50]:
        for shard_key, mapped_node_id in obj.shard_map.items():
            if mapped_node_id == node.node_id:
                target_shard = shard_key  # e.g., '0:2'
                target_obj = obj
                break
        if target_shard:
            break
            
    if not target_shard:
        return  # Node has no shards attached yet
        
    chunk_idx, shard_idx = target_shard.split(':')
    url = f"{node.endpoint}/shard/{target_obj.root_hash}/{chunk_idx}/{shard_idx}"
    
    try:
        with httpx.Client(timeout=10.0) as client:
            # We use a HEAD request or a ranged GET just to check presence,
            # but getting the whole 256KB shard is fast enough for a PoR ping.
            response = client.get(url)
            
            if response.status_code == 200:
                _update_node_reputation(node.id, success=True)
                logger.debug(f"Audit passed for {node.node_id}")
            else:
                _update_node_reputation(node.id, success=False)
                logger.warning(f"Audit failed for {node.node_id} (HTTP {response.status_code})")
    except Exception as e:
        _update_node_reputation(node.id, success=False)
        logger.warning(f"Audit failed for {node.node_id} (Timeout/Error: {e})")

def _update_node_reputation(node_pk, success: bool):
    with transaction.atomic():
        try:
            node = StorageNode.objects.select_for_update().get(pk=node_pk)
            if success:
                node.successful_retrievals += 1
                # Slowly regain reputation
                if node.reputation_score < 100:
                    node.reputation_score = min(100, node.reputation_score + 1)
            else:
                node.failed_retrievals += 1
                # Slash reputation harshly for losing data
                node.reputation_score = max(0, node.reputation_score - 10)
                
                # Auto-disable node if reputation drops too low
                if node.reputation_score <= 10:
                    node.is_active = False
                    logger.critical(f"Node {node.node_id} deactivated due to critical reputation loss.")
                    
            node.save()
        except StorageNode.DoesNotExist:
            pass
