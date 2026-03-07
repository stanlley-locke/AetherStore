import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aetherstore.settings')
django.setup()

from apps.storage.models import EncryptedObject, Bucket, NameRecord

def main():
    owner_did = "did:example:test_user"
    bucket_name = "classic_literature"
    
    bucket = Bucket.objects.filter(name=bucket_name).first()
    obj = EncryptedObject.objects.filter(bucket=bucket).first()
    
    if not obj:
        print("No object found to name.")
        return
        
    print(f"Creating name 'latest-book' for object {obj.id}")
    
    # Create name
    record, created = NameRecord.objects.get_or_create(
        name='latest-book',
        defaults={'owner_did': owner_did, 'target_object': obj}
    )
    
    if not created:
        record.target_object = obj
        record.save()
        
    print(f"NameRecord saved: {record.name} -> {record.target_object.id}")
    
    # Verify retrieval
    fetched = NameRecord.objects.get(name='latest-book')
    print(f"Fetched name: {fetched.name} -> {fetched.target_object.id}")

if __name__ == '__main__':
    main()
