from celery import shared_task
import logging
import httpx
import base64
from pathlib import Path

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_download(self, object_id, owner_did):
    """
    Process file download securely in the background: retrieve chunks, erasure decode, 
    trim padding, verify Merkle DAG, decrypt via AES-GCM, and save to local disk.
    """
    try:
        from apps.storage.models import EncryptedObject, StorageNode
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
        
        logger.info(f"Starting async download for object {object_id}")
        obj = EncryptedObject.objects.get(id=object_id, is_deleted=False)
        
        if obj.owner_did != owner_did:
            raise Exception("Access Denied")
            
        engine = get_erasure_engine()
        decrypted_chunks = {}
        encrypted_chunks = {}
        merkle_dag = MerkleDAG.from_dict(obj.merkle_dag)
        
        metadata = obj.merkle_dag.get('metadata', {}) or {}
        strategy = metadata.get('encryption_strategy', 'legacy')
        
        # Setup decryption for per-chunk or legacy
        salt_b64 = metadata.get('salt')
        if not salt_b64:
            # Fallback for old files without explicit salt
            encryption_fallback = ClientEncryption.for_user(owner_did)
            salt_b64 = base64.b64encode(encryption_fallback.salt).decode('utf-8')
            
        salt = base64.b64decode(salt_b64)
        encryption = ClientEncryption(password=f'{owner_did}:{salt.hex()}', salt=salt)
        
        logger.info(f"Fetching {obj.chunk_count} chunks (strategy: {strategy})...")
        with httpx.Client(timeout=30.0) as client:
            for chunk_index in range(obj.chunk_count):
                chunk_shards = {}
                for key, node_id in obj.shard_map.items():
                    stored_chunk_idx, stored_shard_idx = map(int, key.split(':'))
                    if stored_chunk_idx == chunk_index:
                        try:
                            node = StorageNode.objects.get(node_id=node_id, is_active=True)
                            resp = client.get(
                                f"{node.endpoint}/shard/{obj.root_hash}/{chunk_index}/{stored_shard_idx}"
                            )
                            if resp.status_code == 200:
                                chunk_shards[stored_shard_idx] = resp.content
                        except Exception as e:
                            logger.warning(f"Failed to fetch shard {stored_shard_idx} from {node_id}: {e}")
                
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
