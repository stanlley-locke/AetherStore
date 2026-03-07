import os
import django
import httpx

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aetherstore.settings')
django.setup()

from apps.storage.services.merkle_service import MerkleService
from apps.storage.engine import get_erasure_engine

def test_chunk_upload():
    with open('shakespear.txt', 'rb') as f:
        data_bytes = f.read()
        
    engine = get_erasure_engine()
    
    merkle_dag = MerkleService.build_merkle_dag(data_bytes)
    chunk_meta = merkle_dag.chunks[0]
    
    plaintext_chunk = MerkleService.get_chunk_from_data(
        data_bytes, 0, merkle_dag.chunk_size
    )
    
    # Just pass the plaintext chunk into the erasure coder to test serialization length
    shards = engine.encode(plaintext_chunk)
    shard_data = shards[0]
    
    url = f"http://localhost:8001/shard/{merkle_dag.root_hash}/0/0"
    print(f"Uploading size {len(shard_data)} to {url}")
    
    with httpx.Client() as client:
        response = client.put(url, content=shard_data)
        print(f"Status: {response.status_code}")
        print(f"Content: {response.text}")

if __name__ == "__main__":
    test_chunk_upload()
