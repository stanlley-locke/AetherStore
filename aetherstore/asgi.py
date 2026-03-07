"""
ASGI config for AetherStore — HTTP + WebSocket (Phase 11)
Supports both standard Django HTTP and Django Channels WebSocket.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aetherstore.settings')
django.setup()

from django.core.asgi import get_asgi_application

try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from apps.messaging.routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        'http': get_asgi_application(),
        'websocket': AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })
except ImportError:
    # Fall back to plain ASGI if channels is not installed
    application = get_asgi_application()
