from django.db import models
from django.utils import timezone
import uuid

class UserWallet(models.Model):
    """Tracks the token balance for a user DID."""
    did = models.CharField(max_length=255, unique=True, primary_key=True)
    balance = models.DecimalField(max_digits=20, decimal_places=8, default=100.0) # Start with 100 free tokens
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.did} - Balance: {self.balance} ATK"


class NodeWallet(models.Model):
    """Tracks the token earnings for a P2P Storage Node."""
    node_id = models.CharField(max_length=255, unique=True, primary_key=True)
    earned_balance = models.DecimalField(max_digits=20, decimal_places=8, default=0.0)
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
