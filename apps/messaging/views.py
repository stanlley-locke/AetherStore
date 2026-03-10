"""
Messaging Views — Phases 10-14
Covers: DM/Group conversations, encrypted message send/receive,
file attachments, inbox polling, group key management, and message search.
"""
import hashlib
import logging
import os
from datetime import datetime, timezone, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone as dj_timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# ─── Billing constants ────────────────────────────────────────────────────────
TEXT_MSG_COST = 0.01     # credits per text message
FILE_MSG_COST = 0.05     # credits per file-attached message
GROUP_MSG_MULTIPLIER = 1 # multiplied by member count for group messages


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _owner_did(request):
    did = getattr(request.user, 'did', str(request.user))
    if did and did.startswith('ath1'):
        return f"did:aether:{did}"
    return did


def _encrypt_message(plaintext: str, sender_did: str, recipient_key_id: str) -> str:
    """
    Encrypt a message body using AES-256-GCM.
    Key is derived from HKDF(sender_did:recipient_key_id) so both parties can decrypt.
    Returns a JSON string containing all fields needed for decryption.
    """
    import json
    from apps.core.crypto import ClientEncryption
    password = f"{sender_did}:{recipient_key_id}"
    salt = hashlib.sha256(password.encode()).digest()[:16]
    enc = ClientEncryption(password=password, salt=salt)
    package = enc.encrypt(plaintext.encode())
    # Store the full package as JSON so the decrypt side has nonce/salt/auth_tag
    return json.dumps(package)


def _decrypt_message(ciphertext_json: str, sender_did: str, recipient_key_id: str) -> str:
    """Decrypt a message body. Both sender and recipient can decrypt using the shared key."""
    import json
    from apps.core.crypto import ClientEncryption
    password = f"{sender_did}:{recipient_key_id}"
    salt = hashlib.sha256(password.encode()).digest()[:16]
    enc = ClientEncryption(password=password, salt=salt)
    try:
        package = json.loads(ciphertext_json)
    except (json.JSONDecodeError, TypeError):
        # Legacy: treat as raw base64 combined format
        package = {'encrypted_data': ciphertext_json}
    return enc.decrypt(package).decode('utf-8', errors='replace')


def _charge_wallet(did: str, amount: float, description: str) -> bool:
    """Deduct credits from user wallet. Returns True if successful."""
    from decimal import Decimal
    from apps.billing.models import UserWallet, Transaction
    try:
        wallet, _ = UserWallet.objects.get_or_create(
            did=did,
            defaults={'balance': Decimal('100.00')}
        )
        amt = Decimal(str(amount))
        if wallet.balance < amt:
            return False
        wallet.balance -= amt
        wallet.save()
        Transaction.objects.create(
            user_wallet=wallet,
            tx_type='storage_payment', # or 'debit' technically, but storage_payment fits the schema better
            amount=amt,
            description=description
        )
        return True
    except Exception as e:
        logger.warning(f"Billing failed for {did}: {e}")
        return True  # Don't block messaging on billing errors during dev


def _write_dht_mailbox(conv_id, msg_id, recipient_did, envelope: dict):
    """
    Register a message in the DHT under the recipient mailbox key.
    Stores the full encrypted envelope (Phase 15).
    """
    try:
        from apps.core.dht import dht_service
        from asgiref.sync import async_to_sync
        dht = dht_service.get_node()
        # Key: inbox:did:bob (hashed)
        normalized_did = recipient_did
        if normalized_did.startswith('ath1') and not normalized_did.startswith('did:aether:'):
            normalized_did = f"did:aether:{normalized_did}"
            
        mailbox_key = hashlib.sha1(f"inbox:{normalized_did}".encode()).hexdigest()
        
        # Phase 15: Use find_value to avoid overwriting distributed mailbox
        current_inbox = async_to_sync(dht.find_value)(mailbox_key) or []
        if isinstance(current_inbox, list):
            # Keep only last 50 pointers in DHT to save memory on storage nodes
            current_inbox.append(envelope)
            current_inbox = current_inbox[-50:]
            dht.store(mailbox_key, current_inbox, ttl=86400 * 7) # Keep for 7 days
            logger.info(f"[DHT] Mailbox updated for {recipient_did} (Key: {mailbox_key[:8]})")
            
        # Also store the message content by its own ID for direct access
        content_key = hashlib.sha1(f"msg:content:{msg_id}".encode()).hexdigest()
        dht.store(content_key, envelope, ttl=86400 * 7)
        logger.info(f"[DHT] Message content stored (Key: {content_key[:8]})")
        
    except Exception as e:
        logger.warning(f"DHT mailbox write failed: {e}")


def _push_ws_notification(conversation_id: str, message_data: dict):
    """Push a WebSocket notification to conversation participants (Phase 11)."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        group_name = f"conversation_{str(conversation_id).replace('-', '_')}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {'type': 'new_message', 'message': message_data}
        )
    except Exception as e:
        logger.debug(f"WebSocket push skipped (channels not available): {e}")


# ─── Phase 10: Core Conversations & Messaging ────────────────────────────────

class ConversationListView(APIView):
    """List all conversations for the authenticated user, or create a new one."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.messaging.models import Conversation, ConversationMember
        did = _owner_did(request)
        # Normalize: handle queries with/without prefix if needed, but _owner_did should handle it.
        conv_ids = ConversationMember.objects.filter(did=did).values_list('conversation_id', flat=True)
        conversations = Conversation.objects.filter(id__in=conv_ids).order_by('-updated_at')

        data = []
        for conv in conversations:
            members = list(ConversationMember.objects.filter(conversation=conv).values('did', 'last_read_at'))
            latest = conv.messages.last()
            data.append({
                'id': str(conv.id),
                'name': conv.name,
                'is_group': conv.is_group,
                'channel_name': conv.channel_name,
                'members': [m['did'] for m in members],
                'created_at': conv.created_at.isoformat(),
                'updated_at': conv.updated_at.isoformat(),
                'last_message': {
                    'sender': latest.sender_did,
                    'type': latest.message_type,
                    'sent_at': latest.sent_at.isoformat(),
                } if latest else None,
            })

        return Response({'conversations': data, 'count': len(data)})

    def post(self, request):
        """Create a new DM or group conversation."""
        from apps.messaging.models import Conversation, ConversationMember
        did = _owner_did(request)
        participants = request.data.get('participants', [])
        name = request.data.get('name')
        channel_name = request.data.get('channel_name')

        if not participants:
            return Response({'error': 'participants is required'}, status=400)

        # Ensure creator is always a participant and all are prefixed
        prefixed_participants = []
        for p in participants:
            if p.startswith('ath1') and not p.startswith('did:aether:'):
                prefixed_participants.append(f"did:aether:{p}")
            else:
                prefixed_participants.append(p)
                
        all_participants = list(set([did] + prefixed_participants))
        is_group = len(all_participants) > 2

        # For DM, check if conversation already exists between these two
        if not is_group and len(all_participants) == 2:
            other_did = [p for p in all_participants if p != did][0]
            existing = ConversationMember.objects.filter(
                did=did
            ).values_list('conversation_id', flat=True)
            shared = ConversationMember.objects.filter(
                conversation_id__in=existing, did=other_did
            ).first()
            if shared:
                conv = Conversation.objects.get(id=shared.conversation_id)
                return Response({
                    'id': str(conv.id),
                    'name': conv.name,
                    'is_group': conv.is_group,
                    'members': all_participants,
                    'action': 'existing'
                })

        with transaction.atomic():
            conv = Conversation.objects.create(
                name=name or (f"Group: {', '.join(all_participants[:2])}..." if is_group else None),
                is_group=is_group,
                channel_name=channel_name,
                created_by=did,
            )
            for participant_did in all_participants:
                ConversationMember.objects.create(conversation=conv, did=participant_did)

            # Register @channel name via NameRecord (Phase 13)
            if channel_name:
                try:
                    from apps.core.dht import dht_service
                    dht = dht_service.get_node()
                    dht.store(f"channel:{channel_name}", str(conv.id))
                except Exception as e:
                    logger.warning(f"DHT channel registration failed: {e}")

            # Phase 27: Announce conversation to DHT mailboxes of ALL participants
            init_envelope = {
                'id': f"init-{str(conv.id)}",
                'conversation_id': str(conv.id),
                'conversation_name': conv.name,
                'is_group': is_group,
                'sender_did': did,
                'message_type': 'system',
                'encrypted_body': 'Conversation created',
                'sent_at': dj_timezone.now().isoformat(),
            }
            for p_did in all_participants:
                _write_dht_mailbox(conv.id, init_envelope['id'], p_did, init_envelope)

        return Response({
            'id': str(conv.id),
            'name': conv.name,
            'is_group': is_group,
            'channel_name': channel_name,
            'members': all_participants,
            'action': 'created'
        }, status=status.HTTP_201_CREATED)


class ConversationDetailView(APIView):
    """Get conversation details + paginated message history (Phase 14)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, conversation_id):
        from apps.messaging.models import Conversation, ConversationMember, Message
        did = _owner_did(request)
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        before = request.GET.get('before')

        try:
            conv_obj = Conversation.objects.get(id=conversation_id)
            qs = Message.objects.filter(conversation=conv_obj)
            if before:
                qs = qs.filter(sent_at__lt=before)
            qs = qs.order_by('-sent_at')
            total = qs.count()
            messages_list = qs[(page-1)*page_size : page*page_size]
            
            # Mark last_read_at
            ConversationMember.objects.filter(conversation=conv_obj, did=did).update(
                last_read_at=dj_timezone.now()
            )
            
            members = list(ConversationMember.objects.filter(conversation=conv_obj).values('did', 'last_read_at'))
            conv_resp = {
                'id': str(conv_obj.id),
                'name': conv_obj.name,
                'is_group': conv_obj.is_group,
                'channel_name': conv_obj.channel_name,
                'members': [m['did'] for m in members],
            }
            serialized_msgs = [_serialize_message(m, did) for m in reversed(list(messages_list))]

        except Conversation.DoesNotExist:
            # Phase 27 Fallback: Fetch from DHT
            from apps.core.dht import dht_service
            from asgiref.sync import async_to_sync
            dht = dht_service.get_node()
            mailbox_key_prefixed = hashlib.sha1(f"inbox:{did}".encode()).hexdigest()
            raw_address = did.replace('did:aether:', '')
            mailbox_key_legacy = hashlib.sha1(f"inbox:{raw_address}".encode()).hexdigest()
            
            envelopes_prefixed = async_to_sync(dht.find_value)(mailbox_key_prefixed) or []
            envelopes_legacy = async_to_sync(dht.find_value)(mailbox_key_legacy) or []
            
            seen_ids = set()
            raw_envelopes = []
            for env in (envelopes_prefixed + envelopes_legacy):
                eid = env.get('id')
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    raw_envelopes.append(env)
            
            # Filter for this conversation
            convo_envelopes = [e for e in raw_envelopes if e.get('conversation_id') == str(conversation_id)]
            if not convo_envelopes:
                return Response({'error': 'Conversation not found in DB or DHT'}, status=404)
            
            # Materialize conversation metadata from first envelope
            first = convo_envelopes[0]
            conv_resp = {
                'id': str(conversation_id),
                'name': first.get('conversation_name'),
                'is_group': first.get('is_group', False),
                'members': [did], # Partial member list from DHT view
                'source': 'dht_p2p'
            }
            
            # Sort and paginate envelopes
            convo_envelopes.sort(key=lambda x: x.get('sent_at', ''))
            total = len(convo_envelopes)
            
            # Simple manual serialization of envelopes
            serialized_msgs = []
            for env in convo_envelopes:
                if env.get('id', '').startswith('init-'): continue # skip init helper
                serialized_msgs.append({
                    'id': env['id'],
                    'sender_did': env['sender_did'],
                    'message_type': env['message_type'],
                    'sent_at': env['sent_at'],
                    'encrypted_body': env['encrypted_body'],
                    'is_mine': env['sender_did'] == did,
                    'source': 'dht_p2p'
                })

        return Response({
            'conversation': conv_resp,
            'messages': serialized_msgs,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'has_more': total > page * page_size,
            }
        })

    def delete(self, request, conversation_id):
        """Leave a conversation."""
        from apps.messaging.models import Conversation, ConversationMember
        did = _owner_did(request)
        try:
            conv = Conversation.objects.get(id=conversation_id)
            ConversationMember.objects.filter(conversation=conv, did=did).delete()
            # If no members left, delete conversation
            if not ConversationMember.objects.filter(conversation=conv).exists():
                conv.delete()
            return Response({'status': 'left'})
        except Conversation.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)


def _serialize_message(msg, viewer_did: str) -> dict:
    """Serialize a message for API output."""
    result = {
        'id': str(msg.id),
        'sender_did': msg.sender_did,
        'message_type': msg.message_type,
        'sent_at': msg.sent_at.isoformat(),
        'delivered_at': msg.delivered_at.isoformat() if msg.delivered_at else None,
        'encrypted_body': msg.encrypted_body,
        'is_mine': msg.sender_did == viewer_did,
        'source': getattr(msg, '_from_source', 'database'),
    }
    if hasattr(msg, 'attachment_id') and msg.attachment_id:
        result['attachment'] = {
            'id': str(msg.attachment_id),
            'name': msg.attachment_name,
            'mime': msg.attachment_mime,
            'size': msg.attachment_size,
        }
    return result


class SendMessageView(APIView):
    """Send an encrypted message to a conversation (Phase 10)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, conversation_id):
        from apps.messaging.models import Conversation, ConversationMember, Message
        did = _owner_did(request)

        try:
            conv = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=404)

        if not ConversationMember.objects.filter(conversation=conv, did=did).exists():
            return Response({'error': 'Access denied — you are not in this conversation'}, status=403)

        body = request.data.get('body', '')
        message_type = request.data.get('type', 'text')
        attachment_id = request.data.get('attachment_id')

        if not body and not attachment_id:
            return Response({'error': 'body or attachment is required'}, status=400)

        # Determine recipient DID for key derivation
        members = list(ConversationMember.objects.filter(conversation=conv).exclude(did=did).values_list('did', flat=True))
        if not members:
            return Response({'error': 'No other members in conversation'}, status=400)

        # For DM: key derived from sender+recipient
        # For groups: key derived from sender + conversation_id (group key)
        if conv.is_group:
            recipient_key_id = str(conv.id)
        else:
            recipient_key_id = members[0]

        # Encrypt the message body
        encrypted = _encrypt_message(body, did, recipient_key_id)

        # Billing: charge sender
        cost = TEXT_MSG_COST if message_type == 'text' else FILE_MSG_COST
        if conv.is_group:
            cost *= len(members)
        _charge_wallet(did, cost, f"Message in conversation {conv.id}")

        with transaction.atomic():
            msg_args = {
                'conversation': conv,
                'sender_did': did,
                'message_type': message_type,
                'encrypted_body': encrypted,
                'credits_charged': cost,
                'delivered_at': dj_timezone.now(),
                'search_vector': body[:200],
                'expires_at': (dj_timezone.now() + timedelta(days=conv.message_ttl_days))
                               if conv.message_ttl_days > 0 else None
            }

            if attachment_id:
                from apps.storage.models import EncryptedObject
                try:
                    obj = EncryptedObject.objects.get(id=attachment_id)
                    msg_args['attachment_id'] = obj.id
                    msg_args['attachment_name'] = obj.filename or str(obj.id)
                    msg_args['attachment_mime'] = obj.mime_type
                    msg_args['attachment_size'] = obj.original_size
                except EncryptedObject.DoesNotExist:
                    # Ignore invalid attachment ID but still send the message
                    pass

            msg = Message.objects.create(**msg_args)
            # Bump conversation updated_at
            conv.save()

        # Prepare envelope for DHT (Phase 15)
        envelope = {
            'id': str(msg.id),
            'conversation_id': str(conv.id),
            'conversation_name': conv.name,
            'is_group': conv.is_group,
            'sender_did': did,
            'message_type': message_type,
            'encrypted_body': encrypted,
            'sent_at': msg.sent_at.isoformat(),
            'attachment_id': str(msg.attachment_id) if msg.attachment_id else None,
        }

        # Write to DHT mailboxes for ALL members (including sender)
        all_members = list(ConversationMember.objects.filter(conversation=conv).values_list('did', flat=True))
        for recipient_did in all_members:
            _write_dht_mailbox(conv.id, msg.id, recipient_did, envelope)

        # Push WebSocket notification (Phase 11)
        msg_data = _serialize_message(msg, did)
        _push_ws_notification(conv.id, msg_data)

        # Queue async delivery confirmation (Phase 10 Celery)
        try:
            from workers.message_delivery import confirm_delivery
            confirm_delivery.apply_async(args=[str(msg.id)], countdown=1)
        except Exception as e:
            logger.debug(f"Async delivery task skipped: {e}")

        return Response({
            'id': str(msg.id),
            'status': 'sent',
            'encrypted': True,
            'cost': float(cost),
            'sent_at': msg.sent_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class InboxView(APIView):
    """Poll for new unread messages across all conversations (Phase 10)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.messaging.models import Conversation, ConversationMember, Message
        did = _owner_did(request)

        conv_memberships = ConversationMember.objects.filter(did=did).select_related('conversation')

        inbox = []
        total_unread = 0

        for membership in conv_memberships:
            conv = membership.conversation
            since = membership.last_read_at

            unread_qs = Message.objects.filter(conversation=conv).exclude(sender_did=did)
            if since:
                unread_qs = unread_qs.filter(sent_at__gt=since)

            unread_count = unread_qs.count()
            total_unread += unread_count
            latest_unread = unread_qs.order_by('-sent_at').first()

            if unread_count > 0:
                inbox.append({
                    'conversation_id': str(conv.id),
                    'conversation_name': conv.name,
                    'is_group': conv.is_group,
                    'unread_count': unread_count,
                    'latest_message': _serialize_message(latest_unread, did) if latest_unread else None,
                })

        # Apply limit to conversations
        limit = request.query_params.get('limit')
        if limit and limit.isdigit():
            inbox = sorted(inbox, key=lambda x: x.get('latest_message', {}).get('sent_at', ''), reverse=True)[:int(limit)]

        return Response({
            'total_unread': total_unread,
            'source': 'database',
            'conversations': sorted(inbox, key=lambda x: x['unread_count'], reverse=True),
        })


class DHTInboxView(APIView):
    """
    Directly query the DHT for new messages (Phase 15).
    Allows message retrieval even if the central database is offline.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.core.dht import dht_service
        from asgiref.sync import async_to_sync
        did = _owner_did(request)
        
        dht = dht_service.get_node()
        
        # Check both prefixed and non-prefixed keys for robustness during transition
        mailbox_key_prefixed = hashlib.sha1(f"inbox:{did}".encode()).hexdigest()
        raw_address = did.replace('did:aether:', '')
        mailbox_key_legacy = hashlib.sha1(f"inbox:{raw_address}".encode()).hexdigest()
        
        # Query DHT for both
        envelopes_prefixed = async_to_sync(dht.find_value)(mailbox_key_prefixed) or []
        envelopes_legacy = async_to_sync(dht.find_value)(mailbox_key_legacy) or []
        
        # Combine and deduplicate by message id
        seen_ids = set()
        raw_envelopes = []
        for env in (envelopes_prefixed + envelopes_legacy):
            eid = env.get('id')
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                raw_envelopes.append(env)
        
        # Phase 27: Group envelopes by conversation_id
        convos_map = {}
        for env in raw_envelopes:
            cid = env.get('conversation_id')
            if not cid: continue
            
            if cid not in convos_map:
                convos_map[cid] = {
                    'conversation_id': cid,
                    'conversation_name': env.get('conversation_name'),
                    'is_group': env.get('is_group', False),
                    'messages': [],
                    'unread_count': 0
                }
            
            convos_map[cid]['messages'].append(env)
            # Simple heuristic for unread: if we haven't seen it in DB last_read_at
            # But since we are DHT-first, we'll just report total count for now
            # or use logic if we want to be fancy. For now, let's just use the latest message.

        inbox_data = []
        for cid, data in convos_map.items():
            # Sort messages in this convo by sent_at
            data['messages'].sort(key=lambda x: x.get('sent_at', ''))
            latest = data['messages'][-1]
            
            inbox_data.append({
                'conversation_id': cid,
                'conversation_name': data['conversation_name'],
                'is_group': data['is_group'],
                'unread_count': len(data['messages']), # In DHT mode, we show total history segment as "unread" or "new"
                'latest_message': {
                    'id': latest['id'],
                    'sender_did': latest['sender_did'],
                    'message_type': latest['message_type'],
                    'sent_at': latest['sent_at'],
                    'body': latest['encrypted_body'], # Already encrypted package
                }
            })

        # Sort conversations by latest message time
        inbox_data.sort(key=lambda x: x['latest_message']['sent_at'], reverse=True)

        return Response({
            'total_unread': sum(c['unread_count'] for c in inbox_data),
            'source': 'dht_p2p',
            'conversations': inbox_data
        })


class MessageDecryptView(APIView):
    """Decrypt a message for the authenticated user (returns plaintext)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, conversation_id, message_id):
        from apps.messaging.models import Message, ConversationMember
        did = _owner_did(request)

        try:
            msg = Message.objects.get(id=message_id)
        except Message.DoesNotExist:
            # Phase 15: Fallback to DHT retrieval
            try:
                from apps.core.dht import dht_service
                from asgiref.sync import async_to_sync
                dht = dht_service.get_node()
                content_key = hashlib.sha1(f"msg:content:{message_id}".encode()).hexdigest()
                envelope = async_to_sync(dht.find_value)(content_key)
                
                if not envelope:
                    return Response({'error': 'Message not found in DB or DHT'}, status=404)
                
                # Check if user is member of recorded conversation in envelope
                if not ConversationMember.objects.filter(conversation_id=envelope['conversation_id'], did=did).exists():
                    return Response({'error': 'Access denied (DHT)'}, status=403)
                
                # Create a temporary Message instance (non-persisted) for the logic below
                from apps.messaging.models import Conversation
                from datetime import datetime
                msg = Message(
                    id=envelope['id'],
                    conversation_id=envelope['conversation_id'],
                    sender_did=envelope['sender_did'],
                    message_type=envelope['message_type'],
                    encrypted_body=envelope['encrypted_body'],
                    sent_at=datetime.fromisoformat(envelope['sent_at'])
                )
                # Mark that this came from DHT
                msg._from_source = 'dht_recovered'
            except Exception as e:
                return Response({'error': f'DHT Recovery failed: {e}'}, status=404)

        if not ConversationMember.objects.filter(conversation=msg.conversation, did=did).exists():
            return Response({'error': 'Access denied'}, status=403)

        conv = msg.conversation
        if conv.is_group:
            recipient_key_id = str(conv.id)
        else:
            members = list(ConversationMember.objects.filter(conversation=conv).exclude(did=did).values_list('did', flat=True))
            recipient_key_id = members[0] if members else msg.sender_did

        try:
            # Derive key: if I'm the sender, encrypt(sender, recipient). If I'm recipient,
            # reconstruct key using sender_did + my DID
            # Mark receipt only if in DB
            if getattr(msg, '_from_source', 'database') == 'database':
                from apps.messaging.models import MessageReceipt
                MessageReceipt.objects.get_or_create(message=msg, reader_did=did)
                msg.read_at = dj_timezone.now()
                msg.save(update_fields=['read_at'])
            
            # Use consistent shared key derivation
            if msg.sender_did == did:
                plaintext = _decrypt_message(msg.encrypted_body, did, recipient_key_id)
            else:
                plaintext = _decrypt_message(msg.encrypted_body, msg.sender_did, did if not conv.is_group else recipient_key_id)

            resp_data = _serialize_message(msg, did)
            resp_data['plaintext'] = plaintext
            return Response(resp_data)

        except Exception as e:
            return Response({'error': f'Decryption failed: {e}'}, status=500)


# ─── Phase 12: File Attachments ──────────────────────────────────────────────

class MessageAttachView(APIView):
    """Attach a file to a message — uploads via existing pipeline (Phase 12)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, conversation_id):
        from apps.messaging.models import Conversation, ConversationMember
        from apps.storage.views import UploadView
        did = _owner_did(request)

        try:
            conv = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=404)

        if not ConversationMember.objects.filter(conversation=conv, did=did).exists():
            return Response({'error': 'Access denied'}, status=403)

        if 'file' not in request.FILES:
            return Response({'error': 'file is required'}, status=400)

        uploaded_file = request.FILES['file']

        # Reuse UploadView: store file to P2P storage as usual
        upload_response = UploadView.as_view()(
            request._request,
            bucket_name='messaging_attachments'
        )

        if upload_response.status_code not in (200, 201, 202):
            return Response({'error': 'File upload failed', 'detail': upload_response.data}, status=500)

        object_id = upload_response.data.get('object_id') or upload_response.data.get('task_id')
        caption = request.data.get('caption', '')
        members = list(ConversationMember.objects.filter(conversation=conv).exclude(did=did).values_list('did', flat=True))
        recipient_key_id = str(conv.id) if conv.is_group else (members[0] if members else did)

        # Build message body: encrypted caption + attachment reference
        body = caption or uploaded_file.name
        encrypted = _encrypt_message(body, did, recipient_key_id)

        _charge_wallet(did, FILE_MSG_COST, f"File attachment in conversation {conv.id}")

        from apps.messaging.models import Message
        msg = Message.objects.create(
            conversation=conv,
            sender_did=did,
            message_type='file',
            encrypted_body=encrypted,
            attachment_id=object_id,
            attachment_name=uploaded_file.name,
            attachment_mime=uploaded_file.content_type,
            attachment_size=uploaded_file.size,
            credits_charged=FILE_MSG_COST,
            delivered_at=dj_timezone.now(),
        )
        conv.save()
        _push_ws_notification(conv.id, _serialize_message(msg, did))

        return Response({
            'id': str(msg.id),
            'status': 'sent',
            'attachment_id': str(object_id),
            'attachment_name': uploaded_file.name,
            'size': uploaded_file.size,
        }, status=201)


# ─── Phase 13: Group Management ──────────────────────────────────────────────

class GroupInviteView(APIView):
    """Add members to a group conversation (Phase 13)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, conversation_id):
        from apps.messaging.models import Conversation, ConversationMember, Message
        did = _owner_did(request)

        try:
            conv = Conversation.objects.get(id=conversation_id, is_group=True)
        except Conversation.DoesNotExist:
            return Response({'error': 'Group conversation not found'}, status=404)

        if not ConversationMember.objects.filter(conversation=conv, did=did).exists():
            return Response({'error': 'Access denied'}, status=403)

        new_members = request.data.get('members', [])
        if not new_members:
            return Response({'error': 'members is required'}, status=400)

        added = []
        for member_did in new_members:
            _, created = ConversationMember.objects.get_or_create(
                conversation=conv, did=member_did
            )
            if created:
                added.append(member_did)

        if added:
            # Post a system message announcing new members
            sys_msg = Message.objects.create(
                conversation=conv,
                sender_did=did,
                message_type='system',
                encrypted_body=_encrypt_message(
                    f"{did} added {', '.join(added)} to the group",
                    did, str(conv.id)
                ),
                delivered_at=dj_timezone.now(),
            )
            conv.save()
            _push_ws_notification(conv.id, _serialize_message(sys_msg, did))

        return Response({'added': added, 'already_members': [m for m in new_members if m not in added]})

    def delete(self, request, conversation_id):
        """Remove a member from a group (admin action)."""
        from apps.messaging.models import Conversation, ConversationMember
        did = _owner_did(request)
        remove_did = request.data.get('did')

        try:
            conv = Conversation.objects.get(id=conversation_id, is_group=True)
        except Conversation.DoesNotExist:
            return Response({'error': 'Group conversation not found'}, status=404)

        if conv.created_by != did and not request.user.is_staff:
            return Response({'error': 'Only the group creator can remove members'}, status=403)

        ConversationMember.objects.filter(conversation=conv, did=remove_did).delete()
        return Response({'removed': remove_did})


# ─── Phase 14: Message Search ─────────────────────────────────────────────────

class MessageSearchView(APIView):
    """Full-text search across message metadata (Phase 14)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.messaging.models import Conversation, ConversationMember, Message
        did = _owner_did(request)
        query = request.query_params.get('q', '').strip()
        conversation_id = request.query_params.get('conversation_id')

        if not query:
            return Response({'error': 'q parameter is required'}, status=400)

        conv_ids = ConversationMember.objects.filter(did=did).values_list('conversation_id', flat=True)

        qs = Message.objects.filter(conversation_id__in=conv_ids)
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)

        # Search against plaintext snippets (search_vector field)
        # and sender_did / message_type metadata
        from django.db.models import Q
        qs = qs.filter(
            Q(search_vector__icontains=query) |
            Q(sender_did__icontains=query) |
            Q(attachment_name__icontains=query) |
            Q(message_type__icontains=query)
        ).order_by('-sent_at')[:50]

        return Response({
            'query': query,
            'results': [_serialize_message(m, did) for m in qs],
            'count': len(list(qs)),
        })


class MessageExpireView(APIView):
    """Admin endpoint to force expire old messages (Phase 14)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_staff:
            return Response({'error': 'Admin only'}, status=403)
        from apps.messaging.models import Message
        now = dj_timezone.now()
        expired = Message.objects.filter(expires_at__lt=now, expires_at__isnull=False)
        count = expired.count()
        expired.delete()
        return Response({'deleted': count, 'expired_before': now.isoformat()})
