"""
Custom CSRF Middleware
Exempts API endpoints that use token-based authentication
"""

from django.middleware.csrf import CsrfViewMiddleware
from django.conf import settings
import re


class CsrfExemptMiddleware(CsrfViewMiddleware):
    """
    CSRF middleware that exempts API paths
    Token-based auth doesn't need CSRF protection
    """
    
    def _exempt_paths(self):
        """Get list of exempt paths from settings"""
        return getattr(settings, 'CSRF_EXEMPT_PATHS', [])
    
    def process_view(self, request, callback, callback_args, callback_kwargs):
        """Check if path should be exempt from CSRF"""
        exempt_paths = self._exempt_paths()
        
        for path_pattern in exempt_paths:
            if re.match(path_pattern, request.path_info):
                setattr(request, '_csrf_exempt', True)
                break
        
        return super().process_view(request, callback, callback_args, callback_kwargs)
