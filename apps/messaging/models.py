"""
Messaging Models
Conversation, Message, ConversationMember, MessageKey, MessageAttachment
"""
import uuid
import hashlib
from django.db import models


class Conversation(models.Model):
    """A DM or group conversation between two or more users"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255, null=True, blank=True)
    is_group = models.BooleanField(default=False)
    # @handle via NameRecord (optional for groups)
    channel_name = models.CharField(max_length=255, null=True, blank=True, unique=True)
    created_by = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Auto-expiry: 0 means no expiry
    message_ttl_days = models.IntegerField(default=0)

    class Meta:
        db_table = 'messaging_conversation'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name or str(self.id)


class ConversationMember(models.Model):
    """Membership record for a conversation participant"""
    id = models.BigAutoField(primary_key=True)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='members')
    did = models.CharField(max_length=255, db_index=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    # Encrypted group key for this member (Phase 13)
    encrypted_group_key = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'messaging_conversation_member'
        unique_together = [['conversation', 'did']]

    def __str__(self):
        return f"{self.did} in {self.conversation_id}"


class Message(models.Model):
    """An encrypted message in a conversation"""
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('file', 'File Attachment'),
        ('image', 'Image'),
        ('voice', 'Voice Note'),
        ('system', 'System Event'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender_did = models.CharField(max_length=255, db_index=True)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')

    # Encrypted payload — ciphertext base64 stored here
    # Encrypted with HKDF(sender_did:recipient_did) for DM or group key for groups
    encrypted_body = models.TextField()

    # DHT location for large message payloads (optional — small msgs inline only)
    dht_key = models.CharField(max_length=128, null=True, blank=True)
    node_endpoint = models.CharField(max_length=255, null=True, blank=True)

    # File attachment (Phase 12) — references an EncryptedObject
    attachment_id = models.UUIDField(null=True, blank=True, db_index=True)
    attachment_name = models.CharField(max_length=255, null=True, blank=True)
    attachment_mime = models.CharField(max_length=100, null=True, blank=True)
    attachment_size = models.BigIntegerField(null=True, blank=True)

    # Delivery state
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Credits charged for this message
    credits_charged = models.DecimalField(max_digits=12, decimal_places=6, default=0)

    # Search index (Phase 14)
    search_vector = models.TextField(null=True, blank=True)  # plaintext snippet for search
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'messaging_message'
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['conversation', 'sent_at']),
            models.Index(fields=['sender_did']),
        ]

    def __str__(self):
        return f"Msg {self.id} from {self.sender_did}"

    @property
    def mailbox_key(self):
        """Compute the DHT mailbox key for this message"""
        return hashlib.sha1(f"mailbox:{self.conversation_id}:{self.id}".encode()).hexdigest()


class MessageReceipt(models.Model):
    """Per-member read receipts for group messages"""
    id = models.BigAutoField(primary_key=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='receipts')
    reader_did = models.CharField(max_length=255, db_index=True)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messaging_message_receipt'
        unique_together = [['message', 'reader_did']]
