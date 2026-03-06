from celery import shared_task
from django.db import transaction
import hashlib
import logging
import time

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_upload(self, object_id, data_bytes, mime_type, bucket_id, owner_did, filename=None, filepath=None, upload_session_id=None):
    """
    Process file upload with encryption, Merkle DAG, and shard distribution
    """
    try:
        from apps.storage.models import EncryptedObject, Bucket, StorageNode
        from apps.storage.services.encryption_service import EncryptionService
        from apps.storage.services.merkle_service import MerkleService
        from apps.core.dht import dht_service
        from apps.p2p.services.node_monitor import node_monitor
        from apps.storage.engine import get_erasure_engine
        from apps.p2p.ring import get_hash_ring
        import httpx
        import base64
        
        import os
        
        # Decode base64 encoded string back to raw bytes or read from file
        if filepath and os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                data_bytes = f.read()
        elif isinstance(data_bytes, str):
            data_bytes = base64.b64decode(data_bytes)
            
        logger.info(f"Processing encrypted upload for bucket {bucket_id}, size {len(data_bytes)} bytes")
        
        # 1. Verify enough healthy nodes
        logger.info("Checking node availability...")
        engine = get_erasure_engine()
        node_verification = node_monitor.verify_enough_nodes(required_count=engine.data_shards)
        
        if not node_verification['success']:
            error_msg = f"Insufficient nodes: {node_verification['message']}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        logger.info(f"✓ {node_verification['available_nodes']} healthy nodes available")
        
        # 2. Extract salt for user encryption
        logger.info("Setting up encryption...")
        from apps.core.crypto import ClientEncryption
        salt = EncryptionService.get_user_salt(owner_did)
        encryption = ClientEncryption(password=f'{owner_did}:{salt.hex()}', salt=salt)
        
        # 3. Build Merkle DAG on PLAINTEXT data
        logger.info("Building Merkle DAG...")
        merkle_dag = MerkleService.build_merkle_dag(data_bytes)
        logger.info(f"Merkle root: {merkle_dag.root_hash[:16]}...")
        
        # 4. Check deduplication on PLAINTEXT root hash
        if EncryptedObject.objects.filter(
            original_hash=merkle_dag.root_hash,
            is_deleted=False
        ).exists():
            logger.info(f"Deduplication hit for {merkle_dag.root_hash[:16]}")
            existing = EncryptedObject.objects.filter(
                original_hash=merkle_dag.root_hash,
                is_deleted=False
            ).first()
            return {
                'status': 'deduplicated',
                'object_id': str(existing.id),
                'root_hash': merkle_dag.root_hash
            }
        
        # 5. Assign original hash
        original_hash = merkle_dag.root_hash
        logger.info(f"Original file hash: {original_hash[:16]}...")
        
        # 6. Get healthy nodes
        healthy_nodes = node_monitor.get_healthy_nodes()
        logger.info(f"Using {len(healthy_nodes)} nodes")
        
        # 7. Encode and distribute shards
        dht = dht_service.get_node()
        ring = get_hash_ring()
        
        shard_map = {}
        shards_stored = 0
        
        for chunk_meta in merkle_dag.chunks:
            chunk_index = chunk_meta.index
            
            plaintext_chunk = MerkleService.get_chunk_from_data(
                data_bytes, 
                chunk_index, 
                merkle_dag.chunk_size
            )
            
            # --- PER-CHUNK ENCRYPTION ---
            encrypted_package = encryption.encrypt(plaintext_chunk)
            encrypted_chunk = base64.b64decode(encrypted_package['encrypted_data'])
            
            # Erasure code the encrypted chunk
            shards = engine.encode(encrypted_chunk)
            
            chunk_shard_map = ring.get_all_nodes_for_object(
                f"{merkle_dag.root_hash}:{chunk_index}",
                len(shards)
            )
            
            with httpx.Client(timeout=30.0) as client:
                for shard_index, shard_data in enumerate(shards):
                    nodes = chunk_shard_map.get(shard_index, [])
                    stored = False
                    
                    for node_id, endpoint in nodes:
                        try:
                            response = client.put(
                                f"{endpoint}/shard/{merkle_dag.root_hash}/{chunk_index}/{shard_index}",
                                content=shard_data,
                                timeout=30.0
                            )
                            
                            if response.status_code == 200:
                                key = f"{chunk_index}:{shard_index}"
                                shard_map[key] = node_id
                                shards_stored += 1
                                stored = True
                                
                                dht.store_shard_location(
                                    merkle_dag.root_hash,
                                    chunk_index,
                                    shard_index,
                                    node_id
                                )
                                logger.debug(f"Shard {chunk_index}:{shard_index} -> {node_id}")
                                break
                                
                        except Exception as e:
                            logger.warning(f"Node {node_id} failed: {e}")
                            continue
                    
                    if not stored:
                        logger.error(f"Failed to store shard {chunk_index}:{shard_index}")
            
            logger.info(f"Chunk {chunk_index}/{merkle_dag.chunk_count} done")
        
        # 8. Verify minimum shards
        min_required = merkle_dag.chunk_count * engine.data_shards
        if shards_stored < min_required:
            error_msg = f"Insufficient shards: {shards_stored}/{min_required}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        logger.info(f"✓ Stored {shards_stored} shards")
        
        # 9. Save to database
        with transaction.atomic():
            bucket = Bucket.objects.get(id=bucket_id)

            # Store encryption metadata. We omit nonce & auth_tag as they are embedded inside the chunks!
            merkle_dag_dict = merkle_dag.to_dict()
            merkle_dag_dict.setdefault('metadata', {})
            merkle_dag_dict['metadata'].update({
                'salt': base64.b64encode(salt).decode('utf-8'),
                'algorithm': 'AES-256-GCM',
                'encryption_strategy': 'per-chunk'
            })

            obj = EncryptedObject.objects.create(
                owner_did=owner_did,
                encryption_algorithm='AES-256-GCM',
                key_hash=encryption.get_key_hash(),
                root_hash=merkle_dag.root_hash,
                merkle_dag=merkle_dag_dict,
                chunk_count=merkle_dag.chunk_count,
                chunk_size=merkle_dag.chunk_size,
                original_size=len(data_bytes),
                original_hash=original_hash,
                mime_type=mime_type,
                filename=filename,
                bucket=bucket,
                shard_map=shard_map,
                version=1
            )
            
            from apps.storage.models import ObjectVersion
            ObjectVersion.objects.create(
                object=obj,
                version_number=1,
                root_hash=merkle_dag.root_hash,
                original_size=len(data_bytes),
                original_hash=original_hash,
                created_by=owner_did
            )
        
        logger.info(f"✓ Upload complete: {merkle_dag.root_hash[:16]}")
        
        # Cleanup temp directory if this was a multipart upload
        if upload_session_id:
            try:
                import shutil
                from apps.storage.models import UploadSession
                temp_dir = os.path.join('data', 'temp_uploads', str(upload_session_id))
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                UploadSession.objects.filter(id=upload_session_id).update(status='completed')
            except Exception as e:
                logger.error(f"Cleanup failed for session {upload_session_id}: {e}")
                
        return {
            'status': 'success',
            'object_id': str(obj.id),
            'root_hash': merkle_dag.root_hash,
            'chunk_count': merkle_dag.chunk_count,
            'shards_stored': shards_stored
        }
        
    except Exception as exc:
        if 'upload_session_id' in locals() and upload_session_id:
            from apps.storage.models import UploadSession
            UploadSession.objects.filter(id=upload_session_id).update(status='failed')
            
        logger.error(f"Upload failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)
