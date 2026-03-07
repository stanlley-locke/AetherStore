"""
MessagingConsumer — Phase 11: Real-time WebSocket Delivery
Uses Django Channels with Redis channel layer.

Connection: ws://localhost:8000/ws/messaging/<conversation_id>/
"""
import json
import logging

logger = logging.getLogger(__name__)


try:
    from channels.generic.websocket import AsyncWebsocketConsumer

    class MessagingConsumer(AsyncWebsocketConsumer):
        """
        WebSocket consumer for real-time message delivery.
        Each conversation has a group channel: conversation_<uuid_no_dashes>
        """

        async def connect(self):
            self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
            self.group_name = f"conversation_{self.conversation_id.replace('-', '_')}"
            self.did = None

            # Extract DID from headers (middleware already validated before WS upgrade)
            # The DID is attached to request.user by DIDAuthenticationMiddleware
            user = self.scope.get('user')
            if user and not getattr(user, 'is_anonymous', True):
                self.did = getattr(user, 'did', str(user))
            else:
                await self.close(code=4001)
                return

            # Verify membership in conversation
            try:
                from channels.db import database_sync_to_async

                @database_sync_to_async
                def check_membership():
                    from apps.messaging.models import ConversationMember
                    return ConversationMember.objects.filter(
                        conversation_id=self.conversation_id,
                        did=self.did
                    ).exists()

                if not await check_membership():
                    await self.close(code=4003)
                    return
            except Exception as e:
                logger.warning(f"WS membership check failed: {e}")

            # Join the conversation group
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

            # Send connected acknowledgment
            await self.send(text_data=json.dumps({
                'type': 'connected',
                'conversation_id': self.conversation_id,
                'did': self.did,
            }))
            logger.info(f"[WS] {self.did} connected to conversation {self.conversation_id}")

        async def disconnect(self, close_code):
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(f"[WS] Disconnected {self.did} from {self.conversation_id}")

        async def receive(self, text_data=None, bytes_data=None):
            """Handle messages sent from the WebSocket client side."""
            try:
                data = json.loads(text_data or '{}')
                msg_type = data.get('type')

                if msg_type == 'ping':
                    await self.send(text_data=json.dumps({'type': 'pong'}))

                elif msg_type == 'send_message':
                    # Client sends message via WS — forward to REST endpoint internally
                    # Or handle inline here for speed
                    body = data.get('body', '')
                    await self._handle_send(body, data.get('message_type', 'text'))

                elif msg_type == 'typing':
                    # Broadcast typing indicator to group
                    await self.channel_layer.group_send(
                        self.group_name,
                        {'type': 'typing_indicator', 'did': self.did}
                    )

            except Exception as e:
                logger.warning(f"[WS] receive error: {e}")

        async def _handle_send(self, body: str, message_type: str):
            """Send a message from WebSocket client to conversation."""
            from channels.db import database_sync_to_async

            @database_sync_to_async
            def create_message():
                from apps.messaging.models import Conversation, ConversationMember, Message
                from apps.messaging.views import _encrypt_message, _charge_wallet, _write_dht_mailbox
                from django.utils import timezone
                import decimal

                conv = Conversation.objects.get(id=self.conversation_id)
                members = list(ConversationMember.objects.filter(
                    conversation=conv
                ).exclude(did=self.did).values_list('did', flat=True))

                recipient_key_id = str(conv.id) if conv.is_group else (members[0] if members else self.did)
                encrypted = _encrypt_message(body, self.did, recipient_key_id)

                _charge_wallet(self.did, 0.01, f"WS message in {conv.id}")

                msg = Message.objects.create(
                    conversation=conv,
                    sender_did=self.did,
                    message_type=message_type,
                    encrypted_body=encrypted,
                    credits_charged=decimal.Decimal('0.01'),
                    delivered_at=timezone.now(),
                    search_vector=body[:50] if len(body) <= 50 else None,
                )
                conv.save()

                for r_did in members:
                    _write_dht_mailbox(conv.id, msg.id, r_did)

                return {
                    'id': str(msg.id),
                    'sender_did': self.did,
                    'message_type': message_type,
                    'sent_at': msg.sent_at.isoformat(),
                    'encrypted_body': encrypted,
                }

            msg_data = await create_message()

            # Broadcast to all conversation members via group channel
            await self.channel_layer.group_send(
                self.group_name,
                {'type': 'new_message', 'message': msg_data}
            )

        # ── Group message handlers ──────────────────────────────────────────

        async def new_message(self, event):
            """Called when a new message is pushed to the group."""
            await self.send(text_data=json.dumps({
                'type': 'new_message',
                'message': event['message']
            }))

        async def typing_indicator(self, event):
            """Called when someone is typing — forward to client."""
            if event.get('did') != self.did:  # Don't echo back to sender
                await self.send(text_data=json.dumps({
                    'type': 'typing',
                    'did': event['did']
                }))

        async def member_joined(self, event):
            await self.send(text_data=json.dumps({
                'type': 'member_joined',
                'did': event['did']
            }))

        async def member_left(self, event):
            await self.send(text_data=json.dumps({
                'type': 'member_left',
                'did': event['did']
            }))

except ImportError:
    # channels not installed — define a stub so imports don't crash
    class MessagingConsumer:  # type: ignore
        """Stub: install django-channels to enable WebSocket support."""
        pass
