from django.core.management.base import BaseCommand
from django.db import connection
from apps.storage.models import EncryptedObject, Bucket
import json
import gzip
from datetime import datetime
import os

class Command(BaseCommand):
    help = "Backup metadata to compressed JSON"
    
    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default='backup.json.gz')
        parser.add_argument('--include-shards', action='store_true')
    
    def handle(self, *args, **options):
        output_file = options['output']
        
        self.stdout.write("Starting metadata backup...")
        
        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.0', # Updated version for EncryptedObject
            'buckets': [],
            'objects': [],
            'quotas': []
        }
        
        # Export buckets
        for bucket in Bucket.objects.all():
            backup_data['buckets'].append({
                'name': bucket.name,
                'owner_did': bucket.owner_did,
                'created_at': bucket.created_at.isoformat()
            })
        
        # Export objects (EncryptedObject)
        for obj in EncryptedObject.objects.filter(is_deleted=False):
            backup_data['objects'].append({
                'id': str(obj.id),
                'filename': obj.filename,
                'root_hash': obj.root_hash,
                'original_hash': obj.original_hash,
                'bucket': obj.bucket.name,
                'mime_type': obj.mime_type,
                'size': obj.original_size,
                'owner_did': obj.owner_did,
                'shard_map': obj.shard_map,
                'encryption_algorithm': obj.encryption_algorithm,
                'key_hash': obj.key_hash,
                'created_at': obj.created_at.isoformat()
            })
        
        # Write compressed backup
        with gzip.open(output_file, 'wt', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2)
        
        file_size = os.path.getsize(output_file)
        self.stdout.write(
            self.style.SUCCESS(
                f'Backup complete: {output_file} ({file_size / 1024:.2f} KB)'
            )
        )