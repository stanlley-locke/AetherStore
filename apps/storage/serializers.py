# apps/storage/serializers.py

from rest_framework import serializers
from apps.storage.models import Bucket, EncryptedObject, StorageNode, StorageQuota

class BucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bucket
        fields = ['id', 'name', 'owner_did', 'created_at']
        read_only_fields = ['id', 'created_at']

class EncryptedObjectSerializer(serializers.ModelSerializer):
    bucket_name = serializers.CharField(source='bucket.name', read_only=True)
    
    class Meta:
        model = EncryptedObject
        fields = ['id', 'original_hash', 'root_hash', 'bucket', 'bucket_name', 'mime_type', 'original_size', 'owner_did', 'shard_map', 'filename', 'created_at', 'updated_at']
        read_only_fields = ['id', 'original_hash', 'root_hash', 'created_at', 'updated_at']

class StorageNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageNode
        fields = ['id', 'node_id', 'endpoint', 'is_active', 'last_heartbeat', 'capacity_bytes', 'used_bytes']
        read_only_fields = ['id', 'last_heartbeat']

class StorageQuotaSerializer(serializers.ModelSerializer):
    usage_percent = serializers.SerializerMethodField()
    
    class Meta:
        model = StorageQuota
        fields = ['owner_did', 'quota_bytes', 'used_bytes', 'usage_percent', 'last_calculated']
    
    def get_usage_percent(self, obj):
        if obj.quota_bytes == 0:
            return 0
        return round((obj.used_bytes / obj.quota_bytes) * 100, 2)