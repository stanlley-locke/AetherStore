# apps/accounts/authentication.py

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from django.core.cache import cache
import time

User = get_user_model()


class DIDAuthentication(BaseAuthentication):
    """
    DID-based authentication for REST API
    """
    
    def authenticate(self, request):
        # CRITICAL: Check the underlying Django request, not DRF wrapper
        # This avoids the recursion issue
        django_request = getattr(request, '_request', request)
        
        # If middleware already authenticated, use that user
        if hasattr(django_request, 'user') and django_request.user.is_authenticated:
            return (django_request.user, None)
            
        # Check if path is exempt from authentication (match middleware logic)
        from .middleware import DIDAuthenticationMiddleware
        path = django_request.path.rstrip('/') or '/'
        if any(path.startswith(p) for p in DIDAuthenticationMiddleware.EXEMPT_PATHS):
            return None
        
        # Otherwise, authenticate from header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header or not auth_header.startswith('DID-Signature '):
            return None
        
        try:
            auth_value = auth_header.replace('DID-Signature ', '')
            parts = auth_value.split(':')
            
            if len(parts) < 6:
                raise AuthenticationFailed(
                    f'Invalid format. Got {len(parts)} parts, need 6. '
                    f'Format: did:method:id:signature:timestamp:nonce'
                )
            
            did = ':'.join(parts[:3])
            signature = parts[3]
            timestamp = parts[4]
            nonce = parts[5]
            
            # Validate timestamp
            current_time = time.time()
            try:
                ts = int(timestamp)
                if abs(current_time - ts) > 300:
                    raise AuthenticationFailed('Timestamp expired')
            except ValueError:
                raise AuthenticationFailed('Invalid timestamp')
            
            # Check nonce
            nonce_key = f"nonce:{nonce}"
            if cache.get(nonce_key):
                raise AuthenticationFailed('Nonce already used')
            cache.set(nonce_key, True, timeout=600)
            
            # Get or create user
            user, created = User.objects.get_or_create(
                username=did,
                defaults={'did': did, 'email': f'{did}@aether.store'}
            )
            
            if not user.is_active:
                raise AuthenticationFailed('User disabled')
            
            return (user, None)
            
        except AuthenticationFailed:
            raise
        except Exception as e:
            raise AuthenticationFailed(f'Auth error: {str(e)}')
    
    def authenticate_header(self, request):
        return 'DID-Signature'