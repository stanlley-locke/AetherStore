# tests/test_upload.py
from django.test import TestCase
from rest_framework.test import APIClient
from apps.storage.models import StorageObject, Bucket
import hashlib

class UploadTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.bucket = Bucket.objects.create(name='test-bucket', owner_did='did:test:123')
    
    def test_upload_deduplication(self):
        """Test that duplicate files are not stored twice"""
        data = b'test content for deduplication'
        content_hash = hashlib.sha256(data).hexdigest()
        
        # First upload
        response1 = self.client.post(
            f'/api/v1/upload/{self.bucket.name}/',
            {'file': data},
            format='multipart'
        )
        
        # Second upload (same content)
        response2 = self.client.post(
            f'/api/v1/upload/{self.bucket.name}/',
            {'file': data},
            format='multipart'
        )
        
        # Should return deduplicated flag
        self.assertEqual(response2.data['deduplicated'], True)
        
        # Only one object in DB
        self.assertEqual(StorageObject.objects.filter(content_hash=content_hash).count(), 1)
    
    def test_erasure_coding_recovery(self):
        """Test that file can be recovered with missing shards"""
        from apps.storage.engine import StorageEngine
        
        engine = StorageEngine(6, 3)
        original_data = b'test data for erasure coding recovery' * 1000
        shards = engine.encode(original_data)
        
        # Remove 3 shards (max parity)
        corrupted_shards = shards.copy()
        for i in range(3):
            corrupted_shards[i] = None
        
        # Should still recover
        recovered_data = engine.decode(corrupted_shards)
        self.assertEqual(recovered_data, original_data)
        
        # Remove 4 shards (more than parity)
        corrupted_shards[3] = None
        with self.assertRaises(Exception):
            engine.decode(corrupted_shards)