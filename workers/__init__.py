# This file makes workers a Python package
# Celery will autodiscover tasks from this package

from .encoder import process_upload
from .auditor import audit_storage_health, repair_object, node_heartbeat

__all__ = [
    'process_upload',
    'audit_storage_health',
    'repair_object',
    'node_heartbeat',
]
