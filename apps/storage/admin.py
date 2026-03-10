from django.contrib import admin
from .models import Bucket, StorageObject, StorageNode, StorageQuota, AccessLog, Webhook, EncryptedObject, ObjectVersion

@admin.register(Bucket)
class BucketAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'owner_did', 'created_at']
    search_fields = ['name', 'owner_did']
    list_filter = ['created_at']

@admin.register(StorageObject)
class StorageObjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'content_hash', 'bucket', 'size', 'owner_did', 'created_at', 'is_deleted']
    search_fields = ['content_hash', 'owner_did']
    list_filter = ['is_deleted', 'created_at', 'bucket']
    readonly_fields = ['id', 'content_hash', 'created_at', 'updated_at']

@admin.register(StorageNode)
class StorageNodeAdmin(admin.ModelAdmin):
    list_display = ['node_id', 'endpoint', 'is_active', 'last_heartbeat', 'used_bytes', 'capacity_bytes']
    search_fields = ['node_id', 'endpoint']
    list_filter = ['is_active', 'last_heartbeat']

@admin.register(StorageQuota)
class StorageQuotaAdmin(admin.ModelAdmin):
    list_display = ['owner_did', 'quota_bytes', 'used_bytes', 'last_calculated']
    search_fields = ['owner_did']

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'object_id', 'user_did', 'action', 'bytes_transferred', 'timestamp', 'status_code']
    search_fields = ['user_did', 'action']
    list_filter = ['action', 'timestamp', 'status_code']
    readonly_fields = ['timestamp']

@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ['id', 'owner_did', 'url', 'is_active', 'created_at']
    search_fields = ['owner_did', 'url']
    list_filter = ['is_active']

@admin.register(EncryptedObject)
class EncryptedObjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'filename', 'owner_did', 'bucket', 'original_size', 'chunk_count', 'created_at']
    search_fields = ['owner_did', 'root_hash', 'original_hash']
    list_filter = ['is_deleted', 'is_public', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']

@admin.register(ObjectVersion)
class ObjectVersionAdmin(admin.ModelAdmin):
    list_display = ['id', 'object', 'version_number', 'original_size', 'created_at', 'created_by']
    search_fields = ['object__id', 'root_hash']
    list_filter = ['created_at']
    readonly_fields = ['id', 'created_at']
