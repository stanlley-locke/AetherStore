# This file makes workers a Python package
# Celery will autodiscover tasks from this package

from .encoder import process_upload
from .auditor import audit_storage_health, repair_object, node_heartbeat
from .decoder import process_download
from .garbage_collector import process_garbage_collection

__all__ = [
    'process_upload',
    'audit_storage_health',
    'repair_object',
    'node_heartbeat',
    'process_download',
    'process_garbage_collection',
    'confirm_delivery',
    'expire_old_messages',
    'index_message_for_search',
    'sync_dht_to_db',
    'cleanup_dht_inbox',
]

from .message_delivery import confirm_delivery, expire_old_messages, index_message_for_search, sync_dht_to_db, cleanup_dht_inbox
