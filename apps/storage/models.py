from django.db import models
from django.utils import timezone
import uuid


class Bucket(models.Model):
    """Logical bucket for object organization"""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    owner_did = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'storage_bucket'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class StorageObject(models.Model):
    """Metadata for stored objects"""
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    content_hash = models.CharField(max_length=64, unique=True, db_index=True)
    bucket = models.ForeignKey(Bucket, on_delete=models.CASCADE, related_name='storage_objects')
    mime_type = models.CharField(max_length=100)
    size = models.BigIntegerField()
    owner_did = models.CharField(max_length=255)
    shard_map = models.JSONField(default=dict)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'storage_object'
        indexes = [
            models.Index(fields=['content_hash']),
            models.Index(fields=['owner_did', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.uuid} - {self.content_hash[:16]}"


class StorageNode(models.Model):
    """P2P storage node registration"""
    id = models.BigAutoField(primary_key=True)
    node_id = models.CharField(max_length=64, unique=True)
    endpoint = models.URLField()
    is_active = models.BooleanField(default=True)
    last_heartbeat = models.DateTimeField(auto_now=True)
    capacity_bytes = models.BigIntegerField(default=0)
    used_bytes = models.BigIntegerField(default=0)
    
    class Meta:
        db_table = 'storage_node'
    
    def __str__(self):
        return self.node_id


class StorageQuota(models.Model):
    """Storage quota per user"""
    id = models.BigAutoField(primary_key=True)
    owner_did = models.CharField(max_length=255, unique=True)
    quota_bytes = models.BigIntegerField(default=10737418240)
    used_bytes = models.BigIntegerField(default=0)
    last_calculated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'storage_quota'
    
    def check_quota(self, additional_bytes: int) -> bool:
        return (self.used_bytes + additional_bytes) <= self.quota_bytes


class AccessLog(models.Model):
    """Access tracking for analytics"""
    id = models.BigAutoField(primary_key=True)
    object = models.ForeignKey(StorageObject, on_delete=models.CASCADE, null=True, blank=True, related_name='access_logs')
    user_did = models.CharField(max_length=255)
    action = models.CharField(max_length=20)
    bytes_transferred = models.BigIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status_code = models.IntegerField(default=200)
    
    class Meta:
        db_table = 'storage_access_log'
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user_did', 'timestamp']),
        ]


class Webhook(models.Model):
    """Webhook endpoints for events"""
    id = models.BigAutoField(primary_key=True)
    owner_did = models.CharField(max_length=255)
    url = models.URLField()
    events = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    secret = models.CharField(max_length=64, default=uuid.uuid4)
    
    class Meta:
        db_table = 'storage_webhook'
