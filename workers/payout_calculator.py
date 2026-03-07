from celery import shared_task
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging
from apps.billing.models import UserWallet, NodeWallet, Transaction
from apps.storage.models import EncryptedObject, Bucket, StorageNode

logger = logging.getLogger(__name__)

# Constants for billing rates (e.g., ATK per GB per day)
STORAGE_RATE_PER_GB_DAY = Decimal('0.001')  # Cost to user
NODE_PAYOUT_PER_GB_DAY = Decimal('0.0008')  # Payout to node
BYTES_PER_GB = Decimal('1073741824')

@shared_task(bind=True)
def calculate_payouts(self):
    """
    Periodic task to calculate daily storage costs for users and payouts for nodes.
    Run this via Celery Beat (e.g., daily at midnight).
    """
    try:
        logger.info("Starting daily billing and payout cycle...")
        
        with transaction.atomic():
            # 1. Charge Users for Storage
            _charge_users_for_storage()
            
            # 2. Reward Nodes for Providing Storage
            _reward_nodes_for_storage()
            
        logger.info("Billing cycle completed successfully.")
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Billing cycle failed: {e}", exc_info=True)
        raise

def _charge_users_for_storage():
    """Calculate and deduct storage costs from users' wallets."""
    from django.db.models import Sum
    
    # Get total active storage grouped by User DID
    user_storage = EncryptedObject.objects.filter(is_deleted=False).values('owner_did').annotate(
        total_bytes=Sum('original_size')
    )
    
    for user_data in user_storage:
        did = user_data['owner_did']
        total_bytes = user_data['total_bytes'] or 0
        
        if total_bytes == 0:
            continue
            
        # Calculate cost
        gb_stored = Decimal(total_bytes) / BYTES_PER_GB
        cost = gb_stored * STORAGE_RATE_PER_GB_DAY
        
        # Deduct from wallet
        wallet, _ = UserWallet.objects.get_or_create(did=did)
        wallet.balance -= cost
        wallet.save()
        
        Transaction.objects.create(
            tx_type='storage_payment',
            user_wallet=wallet,
            amount=-cost,
            description=f"Daily storage fee for {total_bytes} bytes"
        )
        logger.debug(f"Charged {did} {cost} ATK for {total_bytes} bytes.")


def _reward_nodes_for_storage():
    """Calculate and reward active nodes for storing chunks."""
    # Fetch active reported capacities from nodes
    active_nodes = StorageNode.objects.filter(is_active=True, last_heartbeat__gte=timezone.now() - timezone.timedelta(hours=24))
    
    for node in active_nodes:
        # In a real system, nodes cryptographically prove exactly how many shards they hold.
        # For simulation, we'll reward them based on their currently reported used capacity.
        # Ideally, we verify against `node_monitor`'s active metrics.
        
        # Assumption: The 'used_bytes' field exists on StorageNode (if not, use a default placeholder metric)
        try:
            stored_bytes = node.used_bytes
        except AttributeError:
            # Fallback if capacity_used isn't tracked on the model directly yet
            stored_bytes = 107374182  # Assume 100MB for test node
            
        if stored_bytes <= 0:
            continue
            
        gb_provided = Decimal(str(stored_bytes)) / BYTES_PER_GB
        reward = gb_provided * NODE_PAYOUT_PER_GB_DAY
        
        wallet, _ = NodeWallet.objects.get_or_create(node_id=node.node_id)
        wallet.earned_balance += reward
        wallet.save()
        
        Transaction.objects.create(
            tx_type='node_payout',
            node_wallet=wallet,
            amount=reward,
            description=f"Daily storage reward for providing {stored_bytes} bytes"
        )
        logger.debug(f"Rewarded node {node.node_id} {reward} ATK for {stored_bytes} bytes.")
