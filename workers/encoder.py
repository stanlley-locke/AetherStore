from celery import shared_task
from django.db import transaction
import hashlib
import logging
import time

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_upload(self, object_id, data_bytes, mime_type, bucket_id, owner_did, filename=None):
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
        
        # Decode base64 encoded string back to raw bytes
        if isinstance(data_bytes, str):
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
        
        # 2. Encrypt data FIRST (before any deduplication)
        logger.info("Encrypting data...")
        encrypted_package = EncryptionService.encrypt_file(data_bytes, owner_did, metadata={
            'filename': filename,
            'mime_type': mime_type
        })
        encrypted_data = encrypted_package['encrypted_data'].encode('utf-8')
        logger.info(f"Encrypted size: {len(encrypted_data)} bytes")
        
        # 3. Build Merkle DAG on encrypted data
        logger.info("Building Merkle DAG...")
        merkle_dag = MerkleService.build_merkle_dag(encrypted_data)
        logger.info(f"Merkle root: {merkle_dag.root_hash[:16]}...")
        
        # 4. Check deduplication on ENCRYPTED root hash (NOT original)
        if EncryptedObject.objects.filter(
            root_hash=merkle_dag.root_hash,  # Check encrypted Merkle root
            is_deleted=False
        ).exists():
            logger.info(f"Deduplication hit for {merkle_dag.root_hash[:16]}")
            existing = EncryptedObject.objects.get(
                root_hash=merkle_dag.root_hash,
                is_deleted=False
            )
            return {
                'status': 'deduplicated',
                'object_id': str(existing.id),
                'root_hash': merkle_dag.root_hash
            }
        
        # 5. Compute original hash for metadata only
        original_hash = hashlib.sha256(data_bytes).hexdigest()
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
            
            chunk = MerkleService.get_chunk_from_data(
                encrypted_data, 
                chunk_index, 
                merkle_dag.chunk_size
            )
            
            shards = engine.encode(chunk)
            
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

            # Store encryption metadata in merkle_dag for decryption
            merkle_dag_dict = merkle_dag.to_dict()
            merkle_dag_dict.setdefault('metadata', {})
            merkle_dag_dict['metadata'].update({
                'nonce': encrypted_package.get('nonce'),
                'salt': encrypted_package.get('salt'),
                'auth_tag': encrypted_package.get('auth_tag'),
                'algorithm': encrypted_package.get('algorithm', 'AES-256-GCM')
            })

            # Validate that the required metadata was generated
            missing_meta = [k for k in ('nonce', 'salt', 'auth_tag') if not merkle_dag_dict['metadata'].get(k)]
            if missing_meta:
                raise ValueError(f"Missing encryption metadata after encrypting: {missing_meta}")

            obj = EncryptedObject.objects.create(
                owner_did=owner_did,
                encryption_algorithm='AES-256-GCM',
                key_hash=encrypted_package['key_hash'],
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
        
        return {
            'status': 'success',
            'object_id': str(obj.id),
            'root_hash': merkle_dag.root_hash,
            'chunk_count': merkle_dag.chunk_count,
            'shards_stored': shards_stored
        }
        
    except Exception as exc:
        logger.error(f"Upload failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)
