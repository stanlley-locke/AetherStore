"""
Message Delivery Celery Worker (Phase 10)
Handles async delivery confirmation, DHT mailbox cleanup, and retry logic.
Phase 14: Also handles message auto-expiry.
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def confirm_delivery(self, message_id: str):
    """Mark a message as delivered and update DHT mailbox."""
    try:
        import django
        from apps.messaging.models import Message
        from django.utils import timezone

        msg = Message.objects.get(id=message_id)
        if not msg.delivered_at:
            msg.delivered_at = timezone.now()
            msg.save(update_fields=['delivered_at'])

        logger.info(f"[DELIVERY] Message {message_id} confirmed delivered")
        return {'status': 'delivered', 'message_id': message_id}

    except Exception as e:
        logger.error(f"[DELIVERY] Error confirming {message_id}: {e}")
        raise self.retry(exc=e)


@shared_task
def expire_old_messages():
    """
    Phase 14: Automatically delete expired messages.
    Runs on a Celery Beat schedule (every hour).
    """
    from apps.messaging.models import Message
    from django.utils import timezone

    now = timezone.now()
    expired = Message.objects.filter(expires_at__lt=now, expires_at__isnull=False)
    count = expired.count()

    # Delete from DHT if node_endpoint is set
    for msg in expired:
        if msg.node_endpoint and msg.dht_key:
            try:
                import httpx
                httpx.delete(f"{msg.node_endpoint}/shard/{msg.dht_key}/0/0", timeout=5.0)
            except Exception:
                pass

    expired.delete()
    logger.info(f"[EXPIRY] Deleted {count} expired messages")
    return {'deleted': count}


@shared_task
def index_message_for_search(message_id: str, plaintext_snippet: str):
    """
    Phase 14: Update the search_vector for a message.
    Called after send to index searchable fields.
    """
    from apps.messaging.models import Message
    try:
        msg = Message.objects.get(id=message_id)
        msg.search_vector = plaintext_snippet[:200]
        msg.save(update_fields=['search_vector'])
    except Message.DoesNotExist:
        pass
@shared_task
def sync_dht_to_db(user_did: str):
    """
    Phase 15: Pull messages from DHT for a specific user and save to local DB.
    Ensures that decentralised messages are eventually backed up locally.
    """
    import hashlib
    from apps.core.dht import dht_service
    from apps.messaging.models import Message, Conversation
    from django.utils import timezone
    
    from asgiref.sync import async_to_sync
    dht = dht_service.get_node()
    mailbox_key = hashlib.sha1(f"inbox:{user_did}".encode()).hexdigest()
    
    # Use find_value via async_to_sync for network-wide lookup
    envelopes = async_to_sync(dht.find_value)(mailbox_key) or []
    if not envelopes:
        return {'status': 'empty', 'count': 0}

    synced_ids = []
    for env in envelopes:
        msg_id = env['id']
        if not Message.objects.filter(id=msg_id).exists():
            try:
                # Ensure conversation exists locally (stub if needed)
                conv, _ = Conversation.objects.get_or_create(
                    id=env['conversation_id'],
                    defaults={'created_by': env['sender_did'], 'name': 'DHT Recovered'}
                )
                
                Message.objects.create(
                    id=msg_id,
                    conversation=conv,
                    sender_did=env['sender_did'],
                    message_type=env['message_type'],
                    encrypted_body=env['encrypted_body'],
                    sent_at=env['sent_at'],
                    delivered_at=timezone.now()
                )
                synced_ids.append(msg_id)
            except Exception as e:
                logger.error(f"[SYNC] Failed to save {msg_id}: {e}")

    logger.info(f"[SYNC] Synchronized {len(synced_ids)} messages for {user_did}")
    return {'status': 'synced', 'count': len(synced_ids), 'ids': synced_ids}


@shared_task
def cleanup_dht_inbox(user_did: str, synced_ids: list):
    """
    Phase 15: Prune messages from the DHT inbox once they are safely in the DB.
    """
    import hashlib
    from apps.core.dht import dht_service
    
    from asgiref.sync import async_to_sync
    dht = dht_service.get_node()
    mailbox_key = hashlib.sha1(f"inbox:{user_did}".encode()).hexdigest()
    
    current_inbox = async_to_sync(dht.find_value)(mailbox_key) or []
    if not current_inbox:
        return

    # Keep only messages NOT in the synced_ids list
    new_inbox = [m for m in current_inbox if m['id'] not in synced_ids]
    
    if len(new_inbox) != len(current_inbox):
        dht.store(mailbox_key, new_inbox, ttl=86400 * 7)
        logger.info(f"[SYNC] Action: Pruned {len(current_inbox) - len(new_inbox)} synced messages from DHT for {user_did}")
