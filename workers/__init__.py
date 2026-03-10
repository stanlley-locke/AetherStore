# This file makes workers a Python package
# Celery will autodiscover tasks from this package

from .encoder import process_upload
from .auditor import audit_storage_health, repair_object, node_heartbeat
from .decoder import process_download
from .garbage_collector import process_garbage_collection, sweep_deleted_objects
from .message_delivery import confirm_delivery, expire_old_messages, index_message_for_search, sync_dht_to_db, cleanup_dht_inbox
from .storage_auditor import audit_nodes
from .payout_calculator import calculate_payouts

__all__ = [
    'process_upload',
    'audit_storage_health',
    'repair_object',
    'node_heartbeat',
    'process_download',
    'process_garbage_collection',
    'sweep_deleted_objects',
    'confirm_delivery',
    'expire_old_messages',
    'index_message_for_search',
    'sync_dht_to_db',
    'cleanup_dht_inbox',
    'audit_nodes',
    'calculate_payouts',
]
