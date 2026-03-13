import json
import logging
import time
import os
from typing import List, Optional, Dict
from django.conf import settings
from apps.core.dht import dht_service
from apps.core import crypto_wallet
from apps.storage.models import EncryptedObject, Bucket

logger = logging.getLogger(__name__)

class MetadataSyncService:
    """
    Handles decentralized metadata synchronization across AetherStore instances.
    Uses the DHT as a registry for signed file manifests.
    """

    @staticmethod
    def get_federation_secret() -> str:
        """Retrieve the shared federation secret from environment."""
        return os.environ.get('FEDERATION_SECRET') or os.environ.get('SECRET_KEY') or "default_federation_secret"

    @staticmethod
    def publish_file_metadata(file_obj: EncryptedObject):
        """
        Publishes a single file's metadata to the DHT.
        Key: file_meta:{root_hash}
        """
        try:
            # Prepare metadata payload
            payload = {
                'id': str(file_obj.id),
                'filename': file_obj.filename,
                'root_hash': file_obj.root_hash,
                'original_size': file_obj.original_size,
                'original_hash': file_obj.original_hash,
                'mime_type': file_obj.mime_type,
                'encryption_algorithm': file_obj.encryption_algorithm,
                'key_hash': file_obj.key_hash,
                'merkle_dag': file_obj.merkle_dag,
                'shard_map': file_obj.shard_map,
                'chunk_count': file_obj.chunk_count,
                'chunk_size': file_obj.chunk_size,
                'owner_did': file_obj.owner_did,
                'created_at': file_obj.created_at.isoformat() if file_obj.created_at else None,
                'timestamp': time.time()
            }

            # Sign the payload using the shared federation secret
            message = json.dumps(payload, sort_keys=True)
            secret = MetadataSyncService.get_federation_secret()
            signature = crypto_wallet.sign_with_secret(secret, message)
            
            # Wrap with signature
            dht_entry = {
                'content': payload,
                'signature': signature,
                'signer_type': 'federation_shared_secret'
            }
            
            key = f"file_meta:{file_obj.root_hash}"
            dht_service.get_node().store(key, dht_entry, ttl=86400 * 7) # 1 week
            logger.info(f"[Sync] Published metadata for {file_obj.filename} ({file_obj.root_hash[:8]})")
            
            # Update user's file index
            MetadataSyncService._add_to_user_index(file_obj.owner_did, file_obj.root_hash)
            
        except Exception as e:
            logger.error(f"[Sync] Failed to publish metadata: {e}")

    @staticmethod
    def _add_to_user_index(owner_did: str, root_hash: str):
        """Internal: Adds a root_hash to the user's registry index in DHT."""
        key = f"user_files:{owner_did}"
        
        import asyncio
        node = dht_service.get_node()
        secret = MetadataSyncService.get_federation_secret()
        
        async def update_index():
            current_data = await node.find_value(key)
            index = []
            if current_data and isinstance(current_data, dict) and 'content' in current_data:
                # Verify existing index if it exists
                content = current_data['content']
                if crypto_wallet.verify_with_secret(secret, json.dumps(content, sort_keys=True), current_data['signature']):
                    index = content.get('root_hashes', [])
            
            if root_hash not in index:
                index.append(root_hash)
            
            payload = {
                'owner_did': owner_did,
                'root_hashes': index[-100:], # keep last 100 files for now
                'timestamp': time.time()
            }
            
            message = json.dumps(payload, sort_keys=True)
            signature = crypto_wallet.sign_with_secret(secret, message)
            
            node.store(key, {
                'content': payload,
                'signature': signature,
                'signer_type': 'federation_shared_secret'
            }, ttl=86400 * 30) # 1 month
            
        # Run in separate thread/task to avoid blocking
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(update_index())
            else:
                loop.run_until_complete(update_index())
        except Exception as e:
            logger.warning(f"[Sync] Failed to queue index update: {e}")

    @staticmethod
    async def discover_remote_files(owner_did: str):
        """
        Queries the DHT for a user's file index and reconciles local DB.
        """
        key = f"user_files:{owner_did}"
        node = dht_service.get_node()
        secret = MetadataSyncService.get_federation_secret()
        
        logger.info(f"[Sync] Discovering files for {owner_did}...")
        data = await node.find_value(key)
        
        if not data or 'content' not in data:
            logger.info(f"[Sync] No remote files found for {owner_did}")
            return
            
        # Verify signature
        content = data['content']
        signature = data['signature']
        message = json.dumps(content, sort_keys=True)
        
        if not crypto_wallet.verify_with_secret(secret, message, signature):
            logger.warning(f"[Sync] Invalid signature for user index {owner_did}! Federation secret mismatch?")
            return
            
        root_hashes = content.get('root_hashes', [])
        logger.info(f"[Sync] Found {len(root_hashes)} remote files. Reconciling...")
        
        for root_hash in root_hashes:
            await MetadataSyncService.reconcile_file(root_hash)

    @staticmethod
    async def reconcile_file(root_hash: str):
        """Fetches full metadata for a root_hash and creates local record if missing."""
        if EncryptedObject.objects.filter(root_hash=root_hash).exists():
            return # Already have it
            
        key = f"file_meta:{root_hash}"
        node = dht_service.get_node()
        secret = MetadataSyncService.get_federation_secret()
        data = await node.find_value(key)
        
        if not data or 'content' not in data:
            return
            
        content = data['content']
        signature = data['signature']
        message = json.dumps(content, sort_keys=True)
        
        if not crypto_wallet.verify_with_secret(secret, message, signature):
            logger.warning(f"[Sync] Invalid signature for file {root_hash}!")
            return
            
        # Create local record
        try:
            # Ensure bucket exists
            bucket_name = "Synced"
            bucket, _ = Bucket.objects.get_or_create(
                name=bucket_name,
                owner_did=content['owner_did']
            )
            
            EncryptedObject.objects.create(
                id=content['id'],
                owner_did=content['owner_did'],
                filename=content['filename'],
                root_hash=content['root_hash'],
                original_size=content['original_size'],
                original_hash=content['original_hash'],
                mime_type=content['mime_type'],
                encryption_algorithm=content['encryption_algorithm'],
                key_hash=content['key_hash'],
                merkle_dag=content['merkle_dag'],
                shard_map=content['shard_map'],
                chunk_count=content['chunk_count'],
                chunk_size=content['chunk_size'],
                bucket=bucket
            )
            logger.info(f"[Sync] Created local record for {content['filename']} from remote sync")
        except Exception as e:
            logger.error(f"[Sync] Failed to create record for {root_hash}: {e}")
