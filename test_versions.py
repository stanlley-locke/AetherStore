import os
import django
import sys
import base64

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aetherstore.settings')
django.setup()

from apps.storage.models import EncryptedObject, Bucket, ObjectVersion
from workers.encoder import process_upload

def main():
    owner_did = "did:example:test_user"
    bucket_name = "classic_literature"
    filename = "test_versioning.txt"
    
    # Ensure bucket
    bucket, _ = Bucket.objects.get_or_create(name=bucket_name, owner_did=owner_did)
    
    print("Uploading Version 1...")
    data_v1 = b"Hello, world! This is version 1."
    data_v1_b64 = base64.b64encode(data_v1).decode('utf-8')
    
    res1 = process_upload(
        object_id=None,
        data_bytes=data_v1_b64,
        mime_type="text/plain",
        bucket_id=str(bucket.id),
        owner_did=owner_did,
        filename=filename
    )
    print(f"V1 Upload Result: {res1}")
    obj_id = res1['object_id']
    
    print("\nUploading Version 2...")
    data_v2 = b"Hello, world! This is version 2, slightly longer."
    data_v2_b64 = base64.b64encode(data_v2).decode('utf-8')
    
    res2 = process_upload(
        object_id=None,
        data_bytes=data_v2_b64,
        mime_type="text/plain",
        bucket_id=str(bucket.id),
        owner_did=owner_did,
        filename=filename
    )
    print(f"V2 Upload Result: {res2}")
    
    print("\nVerifying DB Records:")
    obj = EncryptedObject.objects.get(id=obj_id)
    print(f"Logical Object: {obj.filename} (v{obj.version}), Root Hash: {obj.root_hash[:16]}...")
    
    versions = ObjectVersion.objects.filter(object=obj).order_by('version_number')
    for v in versions:
        print(f" - Version {v.version_number}: Root Hash {v.root_hash[:16]}..., Original Size: {v.original_size}")

if __name__ == '__main__':
    main()
