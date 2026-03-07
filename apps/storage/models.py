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
    deleted_at = models.DateTimeField(null=True, blank=True)
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
    
    # Phase 7: Reputation System
    reputation_score = models.IntegerField(default=50) # 0 to 100
    successful_retrievals = models.BigIntegerField(default=0)
    failed_retrievals = models.BigIntegerField(default=0)
    average_latency_ms = models.IntegerField(default=0)
    
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


# Add to apps/storage/models.py

class EncryptedObject(models.Model):
    """Encrypted file object with Merkle DAG"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    owner_did = models.CharField(max_length=255, db_index=True)
    
    # Encryption metadata
    encryption_algorithm = models.CharField(max_length=50, default='AES-256-GCM')
    key_hash = models.CharField(max_length=64, db_index=True)
    
    # Merkle DAG
    root_hash = models.CharField(max_length=64, unique=True, db_index=True)
    merkle_dag = models.JSONField(default=dict)
    chunk_count = models.IntegerField(default=0)
    chunk_size = models.IntegerField(default=262144)
    
    # Original file info
    original_size = models.BigIntegerField()
    original_hash = models.CharField(max_length=64)
    mime_type = models.CharField(max_length=100)
    filename = models.CharField(max_length=255, null=True)
    
    # Storage
    bucket = models.ForeignKey(Bucket, on_delete=models.CASCADE, related_name='encrypted_objects')
    shard_map = models.JSONField(default=dict)
    
    # Versioning
    version = models.IntegerField(default=1)
    previous_version = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='next_versions')
    
    # Status
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_public = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'storage_encrypted_object'
        indexes = [
            models.Index(fields=['owner_did', '-created_at']),
            models.Index(fields=['root_hash']),
            models.Index(fields=['bucket', 'is_deleted']),
            models.Index(fields=['original_hash']),
        ]
    
    def __str__(self):
        return f"{self.filename or self.id} ({self.original_size} bytes)"


class ObjectVersion(models.Model):
    """File version history"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    object = models.ForeignKey(EncryptedObject, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    root_hash = models.CharField(max_length=64)
    original_size = models.BigIntegerField()
    original_hash = models.CharField(max_length=64)
    merkle_dag = models.JSONField(default=dict)
    shard_map = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=255)
    change_summary = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'storage_object_version'
        ordering = ['-version_number']
        unique_together = ['object', 'version_number']
        indexes = [
            models.Index(fields=['object', '-version_number']),
        ]
    
    def __str__(self):
        return f"{self.object.id} v{self.version_number}"


class UploadSession(models.Model):
    """Tracks a multipart upload session"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    owner_did = models.CharField(max_length=255, db_index=True)
    bucket = models.ForeignKey(Bucket, on_delete=models.CASCADE, related_name='upload_sessions')
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    total_size = models.BigIntegerField(null=True, blank=True)
    
    # Status: 'initialized', 'uploading', 'processing', 'completed', 'failed'
    status = models.CharField(max_length=20, default='initialized')
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True)
    
    class Meta:
        db_table = 'storage_upload_session'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Upload {self.id} ({self.status})"


class UploadPart(models.Model):
    """Tracks individual parts of a multipart upload"""
    id = models.BigAutoField(primary_key=True)
    session = models.ForeignKey(UploadSession, on_delete=models.CASCADE, related_name='parts')
    part_number = models.IntegerField()
    size = models.IntegerField()
    content_hash = models.CharField(max_length=64)
    temp_filepath = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'storage_upload_part'
        unique_together = ['session', 'part_number']
        ordering = ['part_number']
        
    def __str__(self):
        return f"Part {self.part_number} of {self.session.id}"


class NameRecord(models.Model):
    """Human-readable naming for objects (IPNS style)"""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    owner_did = models.CharField(max_length=255, db_index=True)
    target_object = models.ForeignKey(EncryptedObject, on_delete=models.CASCADE, related_name='name_records')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'storage_name_record'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} -> {self.target_object.id}"