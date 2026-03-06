"""
DID Authentication Middleware
Validates DID-based authentication from Authorization header
"""

from django.http import JsonResponse
from django.core.cache import cache
import time


class DIDAuthenticationMiddleware:
    """
    DID-based authentication middleware
    Authorization Header: DID-Signature <did>:<signature>:<timestamp>:<nonce>
    
    For development: Accepts any valid format (signature not cryptographically verified)
    For production: Verify cryptographic signature against DID document
    """
    
    EXEMPT_PATHS = ['/admin/', '/health/', '/docs/', '/static/', '/api/v1/health/', '/api/v1/metrics/']
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip auth for exempt paths
        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return self.get_response(request)
        
        # Skip auth for OPTIONS (CORS preflight)
        if request.method == 'OPTIONS':
            return self.get_response(request)
        
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            return JsonResponse(
                {'detail': 'Missing Authorization header'}, 
                status=401
            )
        
        if not auth_header.startswith('DID-Signature '):
            return JsonResponse(
                {'detail': 'Invalid authorization type. Use: DID-Signature'}, 
                status=401
            )
        
        try:
            # Parse: DID-Signature <did>:<signature>:<timestamp>:<nonce>
            auth_value = auth_header.replace('DID-Signature ', '')
            parts = auth_value.split(':')
            
            # Handle DID with colons (e.g., did:example:locke)
            # Format: did:method:id:signature:timestamp:nonce
            # Minimum 6 parts: did, method, id, signature, timestamp, nonce
            if len(parts) < 6:
                return JsonResponse(
                    {'detail': f'Invalid DID signature format. Expected did:method:id:signature:timestamp:nonce'}, 
                    status=401
                )
            
            # First 3 parts are DID (did:method:id)
            did = ':'.join(parts[:3])
            signature = parts[3]
            timestamp = parts[4]
            nonce = parts[5]
            
            # Check timestamp freshness (prevent replay attacks)
            current_time = time.time()
            try:
                ts = int(timestamp)
                if abs(current_time - ts) > 300:  # 5 min window
                    return JsonResponse(
                        {'detail': 'Signature timestamp expired'}, 
                        status=401
                    )
            except ValueError:
                return JsonResponse(
                    {'detail': 'Invalid timestamp format'}, 
                    status=401
                )
            
            # Check nonce for replay prevention
            nonce_key = f"nonce:{nonce}"
            if cache.get(nonce_key):
                return JsonResponse(
                    {'detail': 'Nonce already used (replay attack)'}, 
                    status=401
                )
            cache.set(nonce_key, True, timeout=600)
            
            # For development: Skip cryptographic verification
            # For production: Verify signature against DID document
            
            # Get or create user
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            user, created = User.objects.get_or_create(
                username=did,
                defaults={
                    'did': did,
                    'email': f'{did}@aether.store'
                }
            )
            
            if not user.is_active:
                return JsonResponse(
                    {'detail': 'User account disabled'}, 
                    status=401
                )
            
            request.user = user
            
        except Exception as e:
            return JsonResponse(
                {'detail': f'Authentication error: {str(e)}'}, 
                status=401
            )
        
        response = self.get_response(request)
        return response
