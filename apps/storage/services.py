from django.core import signing
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.reverse import reverse
from django.db.models import Q
from apps.storage.models import StorageObject
import hashlib
import hmac

class PresignedURLService:
    """
    Generate and validate HMAC-signed URLs for temporary access
    """
    
    SECRET_KEY = settings.SECRET_KEY.encode()
    DEFAULT_TTL = 3600  # 1 hour
    
    @classmethod
    def generate(cls, object_id: str, owner_did: str, ttl: int = None) -> str:
        """Generate presigned URL"""
        ttl = ttl or cls.DEFAULT_TTL
        expiry = int(timezone.now().timestamp()) + ttl
        
        # Create payload
        payload = {
            'obj': str(object_id),
            'did': owner_did,
            'exp': expiry
        }
        
        # Sign with Django's signer
        token = signing.dumps(payload, salt='presigned_download')
        
        # Build URL
        return f"/api/v1/download/presigned/{token}/"
    
    @classmethod
    def validate(cls, token: str) -> dict:
        """Validate and decode presigned URL token"""
        try:
            payload = signing.loads(token, salt='presigned_download', max_age=cls.DEFAULT_TTL)
            
            # Check expiry
            if payload['exp'] < timezone.now().timestamp():
                raise signing.SignatureExpired("Token expired")
            
            return payload
        except signing.SignatureExpired:
            raise Exception("Presigned URL expired")
        except signing.BadSignature:
            raise Exception("Invalid presigned URL signature")
    
    @classmethod
    def generate_hmac_url(cls, object_id: str, method: str = 'GET', ttl: int = 3600) -> str:
        """
        Alternative: HMAC-SHA256 signed URL (more compatible with S3-style)
        """
        expiry = int(timezone.now().timestamp()) + ttl
        
        # String to sign
        string_to_sign = f"{method}:{object_id}:{expiry}"
        
        # Generate signature
        signature = hmac.new(
            cls.SECRET_KEY,
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Build URL with query params
        return f"/api/v1/download/{object_id}?sig={signature}&exp={expiry}"
    
    @classmethod
    def validate_hmac(cls, object_id: str, signature: str, expiry: int, method: str = 'GET') -> bool:
        """Validate HMAC signature"""
        if expiry < timezone.now().timestamp():
            return False
        
        string_to_sign = f"{method}:{object_id}:{expiry}"
        expected_sig = hmac.new(
            cls.SECRET_KEY,
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_sig)
    



class SearchService:
    """Full-text search for objects"""
    
    @staticmethod
    def search(bucket_name: str, query: str, owner_did: str = None):
        """Search objects by MIME type, bucket, or metadata"""
        queryset = StorageObject.objects.filter(
            bucket__name=bucket_name,
            is_deleted=False
        )
        
        if owner_did:
            queryset = queryset.filter(owner_did=owner_did)
        
        # Search by MIME type
        if query:
            queryset = queryset.filter(
                Q(mime_type__icontains=query) |
                Q(content_hash__icontains=query)
            )
        
        return queryset.order_by('-created_at')
    
    @staticmethod
    def get_objects_by_type(bucket_name: str, mime_prefix: str):
        """Get all objects of a specific type (e.g., video/*)"""
        return StorageObject.objects.filter(
            bucket__name=bucket_name,
            mime_type__startswith=mime_prefix,
            is_deleted=False
        )
    
    @staticmethod
    def get_recent_objects(owner_did: str, limit: int = 50):
        """Get recently uploaded objects"""
        return StorageObject.objects.filter(
            owner_did=owner_did,
            is_deleted=False
        ).order_by('-created_at')[:limit]