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
    def _get_key(cls):
        return hashlib.sha256(cls.SECRET_KEY).digest()

    @classmethod
    def generate(cls, object_id: str, owner_did: str, ttl: int = None) -> str:
        """Generate a short encrypted presigned URL token"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import os
        import base64
        
        ttl = ttl or cls.DEFAULT_TTL
        expiry = int(timezone.now().timestamp()) + ttl
        
        # Binary payload: 16 bytes UUID + 4 bytes Expiry Timestamp (20 bytes total)
        import uuid
        import struct
        uid_bytes = uuid.UUID(str(object_id)).bytes
        exp_bytes = struct.pack('>I', expiry)
        payload = uid_bytes + exp_bytes
        
        # Encrypt
        aesgcm = AESGCM(cls._get_key())
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, payload, None)
        
        # Combine nonce + ciphertext and encode
        token = base64.urlsafe_b64encode(nonce + ct).decode('utf-8').rstrip('=')
        
        # Build URL
        return f"/api/v1/download/presigned/{token}/"
    
    @classmethod
    def validate(cls, token: str) -> dict:
        """Validate and decode short presigned URL token"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import base64
        import struct
        import uuid
        
        try:
            # Re-pad base64
            padding = '=' * (4 - (len(token) % 4))
            raw = base64.urlsafe_b64decode(token + padding)
            
            # Decrypt
            aesgcm = AESGCM(cls._get_key())
            nonce = raw[:12]
            ct = raw[12:]
            payload = aesgcm.decrypt(nonce, ct, None)
            
            # Unpack 20 bytes: 16 UUID + 4 Timestamp
            uid_bytes = payload[:16]
            exp_bytes = payload[16:]
            
            object_id = str(uuid.UUID(bytes=uid_bytes))
            expiry = struct.unpack('>I', exp_bytes)[0]
            
            # Check expiry
            if expiry < timezone.now().timestamp():
                raise Exception("Presigned URL expired")
                
            return {
                'obj': object_id,
                'did': 'presigned', # We drop owner_did encoding to save 50+ bytes
                'exp': expiry
            }
        except Exception as e:
            if "expired" in str(e):
                raise
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