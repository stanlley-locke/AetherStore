from django.core.management.base import BaseCommand
import json
import gzip
from apps.storage.models import EncryptedObject, Bucket
from django.utils import timezone
from datetime import datetime

class Command(BaseCommand):
    help = "Restore metadata from backup"
    
    def add_arguments(self, parser):
        parser.add_argument('--input', type=str, required=True)
        parser.add_argument('--dry-run', action='store_true')
    
    def handle(self, *args, **options):
        input_file = options['input']
        dry_run = options['dry_run']
        
        self.stdout.write(f"Restoring from {input_file}...")
        
        with gzip.open(input_file, 'rt', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        restored_count = 0
        
        for obj_data in backup_data['objects']:
            if dry_run:
                self.stdout.write(f"Would restore: {obj_data['id']}")
                continue
            
            bucket, _ = Bucket.objects.get_or_create(
                name=obj_data['bucket'],
                defaults={'owner_did': obj_data['owner_did']}
            )
            
            obj, created = EncryptedObject.objects.update_or_create(
                id=obj_data['id'],
                defaults={
                    'filename': obj_data.get('filename', f"restored_{obj_data['id'][:8]}"),
                    'root_hash': obj_data.get('root_hash', obj_data.get('content_hash')),
                    'original_hash': obj_data.get('original_hash', obj_data.get('content_hash')),
                    'bucket': bucket,
                    'mime_type': obj_data['mime_type'],
                    'original_size': obj_data.get('size', 0),
                    'owner_did': obj_data['owner_did'],
                    'shard_map': obj_data['shard_map'],
                    'encryption_algorithm': obj_data.get('encryption_algorithm', 'AES-256-GCM'),
                    'key_hash': obj_data.get('key_hash', 'legacy_restored'),
                    'is_deleted': False
                }
            )
            
            if created:
                restored_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Restored {restored_count} objects')
        )