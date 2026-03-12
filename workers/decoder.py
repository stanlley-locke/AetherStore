from celery import shared_task
import logging
import httpx
import base64
from pathlib import Path

logger = logging.getLogger(__name__)

def _update_reputation(node_id: str, success: bool):
    """Dynamically adjust Node reputation during real-time downloads."""
    from apps.storage.models import StorageNode
    from django.db import transaction
    try:
        with transaction.atomic():
            node = StorageNode.objects.select_for_update().get(node_id=node_id, is_active=True)
            if success:
                node.successful_retrievals += 1
                node.reputation_score = min(100, node.reputation_score + 1)
            else:
                node.failed_retrievals += 1
                node.reputation_score = max(0, node.reputation_score - 5)
                if node.reputation_score <= 10:
                    node.is_active = False
                    logger.critical(f"Node {node_id} slashed & deactivated during download.")
            node.save()
    except Exception:
        pass

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_download(self, object_id, owner_did, version_number=None):
    """
    Process file download securely in the background: retrieve chunks, erasure decode, 
    trim padding, verify Merkle DAG, decrypt via AES-GCM, and save to local disk.
    """
    try:
        from apps.storage.models import EncryptedObject, StorageNode, ObjectVersion
        from apps.storage.services.merkle_service import MerkleService
        from apps.storage.engine import get_erasure_engine
        from apps.core.merkle import MerkleDAG
        from apps.core.crypto import ClientEncryption
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        
        # Setup temporary download location
        download_dir = Path("data/downloads")
        download_dir.mkdir(parents=True, exist_ok=True)
        task_id = self.request.id
        output_path = download_dir / f"{task_id}.bin"
        
        logger.info(f"Starting async download for object {object_id} (version: {version_number or 'latest'})")
        obj = EncryptedObject.objects.get(id=object_id, is_deleted=False)
        
        if obj.owner_did != owner_did:
            raise Exception("Access Denied")
            
        active_merkle_dag = obj.merkle_dag
        active_shard_map = obj.shard_map
        active_root_hash = obj.root_hash
        
        if version_number:
            try:
                history = ObjectVersion.objects.get(object=obj, version_number=int(version_number))
                active_merkle_dag = history.merkle_dag
                active_shard_map = history.shard_map
                active_root_hash = history.root_hash
            except ObjectVersion.DoesNotExist:
                raise Exception(f"Version {version_number} not found")

        engine = get_erasure_engine()
        decrypted_chunks = {}
        encrypted_chunks = {}
        merkle_dag = MerkleDAG.from_dict(active_merkle_dag)
        
        metadata = active_merkle_dag.get('metadata', {}) or {}
        strategy = metadata.get('encryption_strategy', 'legacy')
        
        from apps.storage.services.encryption_service import EncryptionService
        encryption = EncryptionService.get_encryption_instance(metadata, owner_did, fallback_hash=active_root_hash)
        
        logger.info(f"Fetching {obj.chunk_count} chunks (strategy: {strategy})...")
        with httpx.Client(timeout=30.0) as client:
            from asgiref.sync import async_to_sync
            from apps.core.dht import dht_service
            dht = dht_service.get_node()
            
            for chunk_index in range(obj.chunk_count):
                chunk_shards = {}
                # In a fully decentralized system, we could query the DHT directly for shards.
                # Here we use the shard_map as a cache, and locate the node via DHT.
                for key, node_id in active_shard_map.items():
                    stored_chunk_idx, stored_shard_idx = map(int, key.split(':'))
                    if stored_chunk_idx == chunk_index:
                        try:
                            # 1. Resolve via DHT 
                            peers = async_to_sync(dht.find_node)(node_id)
                            peer = next((p for p in peers if p.node_id == node_id), None)
                            
                            # 2. Fallback to centralized DB if DHT isn't fully propagated
                            if peer:
                                endpoint = f"http://{peer.address}:{peer.port}"
                            else:
                                node = StorageNode.objects.filter(node_id=node_id, is_active=True).first()
                                if node:
                                    endpoint = node.endpoint
                                else:
                                    raise Exception("Node not located in DHT or SQLite")
                            
                            
                            resp = client.get(
                                f"{endpoint}/shard/{active_root_hash}/{chunk_index}/{stored_shard_idx}"
                            )
                            if resp.status_code == 200:
                                chunk_shards[stored_shard_idx] = resp.content
                                _update_reputation(node_id, success=True)
                            else:
                                logger.warning(f"Node {node_id} failed to serve shard (HTTP {resp.status_code})")
                                _update_reputation(node_id, success=False)
                        except Exception as e:
                            logger.warning(f"Failed to fetch shard {stored_shard_idx} from {node_id}: {e}")
                            _update_reputation(node_id, success=False)
                
                if len(chunk_shards) < engine.data_shards:
                    raise Exception(f"Insufficient shards for chunk {chunk_index}. Found {len(chunk_shards)}/{engine.data_shards}")
                    
                # Decode chunk from available shards
                shard_list = [chunk_shards.get(i, None) for i in range(max(chunk_shards.keys()) + 1)]
                padded_encrypted_chunk = engine.decode(shard_list)
                
                chunk_meta = merkle_dag.chunks[chunk_index]
                
                if strategy == 'per-chunk':
                    # AES-GCM adds exactly 28 bytes (12 nonce + 16 auth_tag)
                    encrypted_chunk_size = chunk_meta.size + 28
                    encrypted_chunk = padded_encrypted_chunk[:encrypted_chunk_size]
                    
                    encrypted_package = {
                        'encrypted_data': base64.b64encode(encrypted_chunk).decode('utf-8'),
                        'salt': salt_b64
                    }
                    plaintext_chunk = encryption.decrypt(encrypted_package)
                    decrypted_chunks[chunk_index] = plaintext_chunk
                    logger.info(f"Successfully decoded and decrypted chunk {chunk_index}")
                else:
                    # Legacy: chunk_meta mapped to the encrypted chunk directly
                    encrypted_chunk_size = chunk_meta.size
                    encrypted_chunk = padded_encrypted_chunk[:encrypted_chunk_size]
                    encrypted_chunks[chunk_index] = encrypted_chunk
                    logger.info(f"Successfully decoded legacy chunk {chunk_index}")

        # Verify Integrity
        logger.info("Verifying Merkle DAG...")
        if strategy == 'per-chunk':
            if not MerkleService.verify_chunks(merkle_dag, decrypted_chunks):
                raise Exception("Merkle verification failed: Tampered or corrupted chunks detected")
            
            # Reassemble plaintext directly
            plaintext = MerkleService.reassemble_file(decrypted_chunks, merkle_dag.total_size)
        else:
            if not MerkleService.verify_chunks(merkle_dag, encrypted_chunks):
                raise Exception("Merkle verification failed: Tampered or corrupted chunks detected")
            
            # Reassemble encrypted blob then decrypt
            encrypted_data = MerkleService.reassemble_file(encrypted_chunks, merkle_dag.total_size)
            logger.info(f"Reassembled legacy core structure, decrypting {len(encrypted_data)} bytes...")
            
            encrypted_data_str = (
                encrypted_data.decode('utf-8')
                if isinstance(encrypted_data, (bytes, bytearray))
                else str(encrypted_data)
            )
            
            encrypted_package = {
                'encrypted_data': encrypted_data_str,
                'salt': salt_b64,
            }
            if metadata.get('nonce'):
                encrypted_package['nonce'] = metadata['nonce']
            if metadata.get('auth_tag'):
                encrypted_package['auth_tag'] = metadata['auth_tag']
                
            plaintext = encryption.decrypt(encrypted_package)
        
        # Write to local cache for streaming
        with open(output_path, 'wb') as f:
            f.write(plaintext)
            
        logger.info(f"File fully downloaded and decrypted to {output_path}")
        
        return {
            'status': 'success',
            'filename': obj.filename,
            'mime_type': obj.mime_type,
            'output_path': str(output_path),
            'size': len(plaintext)
        }
        
    except Exception as e:
        logger.error(f"Download processing failed: {str(e)}")
        raise
