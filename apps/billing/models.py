from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid

class UserWallet(models.Model):
    """Tracks the token balance for a user DID."""
    did = models.CharField(max_length=255, unique=True, primary_key=True)
    address = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)  # ath1... blockchain address
    balance = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('100.0')) # Start with 100 free tokens
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.did} - Balance: {self.balance} ATK"

    @classmethod
    def get_or_create_linked(cls, did: str):
        """
        Retrieves or creates a UserWallet and auto-links it to any pending 
        address-based wallets.
        """
        from .models import Transaction
        import logging
        logger = logging.getLogger(__name__)
        
        wallet, created = cls.objects.get_or_create(did=did)
        
        # Only attempt to link if address is missing and it's a real Aether DID
        if not wallet.address and did.startswith('did:aether:ath1'):
            extracted_address = did.replace('did:aether:', '')
            wallet.address = extracted_address
            wallet.save()
            
            # Check for "pending" wallet created via WalletTransferView
            pending_wallets = cls.objects.filter(address=extracted_address).exclude(did=did)
            for pending in pending_wallets:
                if pending.balance > 0:
                    old_balance = wallet.balance
                    wallet.balance += pending.balance
                    logger.info(f"Merging pending wallet {pending.did} into {wallet.did}. Balance: {old_balance} -> {wallet.balance}")
                    
                    # Move transactions
                    Transaction.objects.filter(user_wallet=pending).update(user_wallet=wallet)
                    
                    # Set pending balance to 0 and delete
                    pending.balance = 0
                    pending.save()
                    pending.delete()
                    wallet.save()
        
        return wallet, created


class NodeWallet(models.Model):
    """Tracks the token earnings for a P2P Storage Node."""
    node_id = models.CharField(max_length=255, unique=True, primary_key=True)
    address = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)  # ath1... blockchain address
    earned_balance = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0.0'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.node_id} - Earned: {self.earned_balance} ATK"


class Transaction(models.Model):
    """Audit trail of all token movements (deposits, storage payments, node payouts)."""
    
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('storage_payment', 'Storage Payment'),
        ('node_payout', 'Node Payout'),
        ('transfer_in', 'Incoming Transfer'),
        ('transfer_out', 'Outgoing Transfer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tx_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    
    # Depending on tx_type, one of these will be populated
    user_wallet = models.ForeignKey(UserWallet, null=True, blank=True, on_delete=models.SET_NULL, related_name='transactions')
    node_wallet = models.ForeignKey(NodeWallet, null=True, blank=True, on_delete=models.SET_NULL, related_name='transactions')
    
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    description = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.user_wallet:
            return f"{self.tx_type.capitalize()} - {self.user_wallet.did}: {self.amount} ATK"
        elif self.node_wallet:
            return f"{self.tx_type.capitalize()} - {self.node_wallet.node_id}: {self.amount} ATK"
        return f"{self.tx_type.capitalize()} - {self.amount} ATK"

class LedgerTransaction(models.Model):
    """Represents a cryptographically signed peer-to-peer token transfer."""
    tx_hash = models.CharField(max_length=64, primary_key=True)
    sender_address = models.CharField(max_length=64, db_index=True)
    recipient_address = models.CharField(max_length=64, db_index=True)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    signature = models.TextField() # Hex string of Ed25519 signature
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')], default='completed')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'billing_ledger_transaction'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.tx_hash[:8]} - {self.amount} ATK from {self.sender_address[:8]} to {self.recipient_address[:8]}"
