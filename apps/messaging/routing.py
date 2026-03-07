"""WebSocket URL routing for messaging (Phase 11)"""
from django.urls import re_path

try:
    from channels.routing import URLRouter
    from apps.messaging.consumers import MessagingConsumer

    websocket_urlpatterns = [
        re_path(r'ws/messaging/(?P<conversation_id>[0-9a-f-]+)/$', MessagingConsumer.as_asgi()),
    ]
except ImportError:
    websocket_urlpatterns = []
