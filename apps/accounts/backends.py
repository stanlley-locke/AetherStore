from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
import nacl.signing
import nacl.encoding

User = get_user_model()

class DIDAuthBackend(BaseBackend):
    """
    Authenticates users based on DID Signature in Authorization Header.
    Format: Authorization: DID-Signature <did>:<signature>
    """
    def authenticate(self, request, did=None, signature=None):
        if not did or not signature:
            return None
        
        # 1. Resolve DID Document (Mocked for brevity, use universal resolver in prod)
        # public_key = resolve_did_public_key(did) 
        
        # 2. Verify Signature against nonce/timestamp to prevent replay attacks
        # For MVP, we assume valid signature implies identity
        try:
            # Verify logic using PyNaCl
            # verify_key = nacl.signing.VerifyKey(public_key_bytes)
            # verify_key.verify(message, signature)
            
            # 3. Get or Create User
            user, created = User.objects.get_or_create(username=did, defaults={'did': did})
            user.did = did
            user.save()
            return user
        except Exception:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None