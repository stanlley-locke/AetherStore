from rest_framework.throttling import SimpleRateThrottle
from django.core.cache import cache
from datetime import timedelta

class DIDRateThrottle(SimpleRateThrottle):
    """
    Rate limiting based on DID identity
    Different limits for upload vs download
    """
    scope = 'upload'
    
    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.did
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

class UploadRateThrottle(DIDRateThrottle):
    rate = '10/hour'  # 10 uploads per hour per DID
    scope = 'upload'

class DownloadRateThrottle(DIDRateThrottle):
    rate = '100/hour'  # 100 downloads per hour per DID
    scope = 'download'

class BurstRateThrottle(SimpleRateThrottle):
    """Prevent API abuse with burst limiting"""
    rate = '30/min'
    scope = 'burst'
    
    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return f"burst:{ident}"