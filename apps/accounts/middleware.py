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
    EXEMPT_PATHS = [
        '/admin', 
        '/health', 
        '/docs', 
        '/static', 
        '/api/v1/storage/health', 
        '/api/v1/storage/metrics', 
        '/api/v1/storage/stats',
        '/api/v1/storage/download/presigned',
        '/api/v1/billing/wallet/transfer', 
        '/api/v1/billing/wallet/recover',
        '/api/v1/billing/wallet/generate',
        '/favicon.ico'
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        path = request.path
        if not path.startswith('/'):
            path = '/' + path
            
        # Standardize path for matching
        normalized_path = path.rstrip('/')
        if not normalized_path:
            normalized_path = '/'

        # Skip auth for exempt paths (prefix match)
        is_exempt = any(normalized_path.startswith(p) for p in self.EXEMPT_PATHS)
        
        # Also check without /api/v1 prefix just in case of proxy issues
        if not is_exempt:
            short_path = normalized_path.replace('/api/v1', '')
            is_exempt = any(short_path.startswith(p.replace('/api/v1', '')) for p in self.EXEMPT_PATHS if p.startswith('/api/v1'))
            
        if is_exempt:
            return self.get_response(request)
        
        # Skip auth for OPTIONS (CORS preflight)
        if request.method == 'OPTIONS':
            return self.get_response(request)
        
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            # Provide more debug info if it fails
            return JsonResponse(
                {'detail': f'Missing Authorization header for path: {request.path}'}, 
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
