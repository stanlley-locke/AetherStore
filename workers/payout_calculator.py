from celery import shared_task
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging
from apps.billing.models import UserWallet, NodeWallet, Transaction
from apps.storage.models import EncryptedObject, Bucket, StorageNode
import httpx

logger = logging.getLogger(__name__)

# Constants for billing rates (e.g., ATK per GB per day)
STORAGE_RATE_PER_GB_DAY = Decimal('0.001')  # Cost to user
NODE_PAYOUT_PER_GB_DAY = Decimal('0.0008')  # Payout to node (base)
NODE_PAYOUT_PER_RETRIEVAL = Decimal('0.000001') # Payout per successful retrieval
BYTES_PER_GB = Decimal('1073741824')
ERASURE_CODING_MULTIPLIER = Decimal('1.5')  # 6 data + 3 parity = 1.5x physical footprint

@shared_task(bind=True)
def calculate_payouts(self):
    """
    Periodic task to calculate daily storage costs for users and payouts for nodes.
    Run this via Celery Beat (e.g., daily at midnight).
    """
    try:
        logger.info("Starting daily billing and payout cycle...")
        
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
            
        with transaction.atomic():
            # Calculate cost based on physical storage footprint (including Erasure fragments)
            gb_stored = (Decimal(total_bytes) / BYTES_PER_GB) * ERASURE_CODING_MULTIPLIER
            cost = gb_stored * STORAGE_RATE_PER_GB_DAY
            
            if cost <= 0:
                continue
                
            # Deduct from wallet
            wallet, _ = UserWallet.objects.get_or_create(did=did)
            wallet.balance = Decimal(str(wallet.balance)) - cost
            wallet.save()
            
            Transaction.objects.create(
                tx_type='storage_payment',
                user_wallet=wallet,
                amount=-cost,
                description=f"Daily storage fee for {total_bytes} bytes (x1.5 EC footprint)"
            )
            logger.debug(f"Charged {did} {cost} ATK for {total_bytes} bytes.")


def _reward_nodes_for_storage():
    """Calculate and reward active nodes for storing chunks."""
    # Fetch active reported capacities from nodes
    active_nodes = StorageNode.objects.filter(is_active=True, last_heartbeat__gte=timezone.now() - timezone.timedelta(hours=24))
    
    for node in active_nodes:
        with transaction.atomic():
            # Basic storage holding
            stored_bytes = node.used_bytes
                
            gb_provided = Decimal(str(stored_bytes)) / BYTES_PER_GB
            base_reward = gb_provided * NODE_PAYOUT_PER_GB_DAY
            
            # Reputation scaling (Max 1.0x, minimum 0.0x for bad nodes)
            # A reputation of 50 yields 0.5x, 100 yields 1.0x
            reputation_multiplier = Decimal(str(max(0, min(100, node.reputation_score)))) / Decimal('100.0')
            storage_reward = base_reward * reputation_multiplier
            
            # Proof of Service Layer: Reward data delivery
            retrieval_reward = Decimal(str(node.successful_retrievals)) * NODE_PAYOUT_PER_RETRIEVAL
            total_reward = storage_reward + retrieval_reward
            
            if total_reward <= 0:
                continue
                
            # Fetch securely sharded node wallet address from network
            wallet_addr = None
            try:
                # Query DHT using the node's local interface
                dht_url = f"{node.endpoint}/dht/get/node_wallet:{node.node_id}"
                resp = httpx.get(dht_url, timeout=2.0)
                if resp.status_code == 200 and resp.json().get('found'):
                    wallet_addr = resp.json().get('value')
            except Exception as e:
                logger.warning(f"DHT wallet lookup failed for {node.node_id}: {e}")
                
            # Execute Ledger Payout
            wallet_credited = False
            if wallet_addr:
                user_wallet = UserWallet.objects.filter(address=wallet_addr).first()
                if user_wallet:
                    # User securely bound their main wallet! Send direct to User
                    user_wallet.balance += total_reward
                    user_wallet.save()
                    Transaction.objects.create(
                        tx_type='node_payout',
                        user_wallet=user_wallet,
                        amount=total_reward,
                        description=f"Node Earnings ({node.node_id}): Storage {stored_bytes}B"
                    )
                    wallet_credited = True
                else:
                    # Anonymous Node operator defined an address
                    node_wallet, _ = NodeWallet.objects.get_or_create(node_id=node.node_id)
                    node_wallet.address = wallet_addr
                    node_wallet.earned_balance += total_reward
                    node_wallet.save()
                    Transaction.objects.create(
                        tx_type='node_payout',
                        node_wallet=node_wallet,
                        amount=total_reward,
                        description=f"Node Earnings: Storage {stored_bytes}B"
                    )
                    wallet_credited = True
                    
            if not wallet_credited:
                # Legacy unmapped node logic (pre-Phase 17)
                wallet, _ = NodeWallet.objects.get_or_create(node_id=node.node_id)
                wallet.earned_balance = Decimal(str(wallet.earned_balance)) + total_reward
                wallet.save()
                
                Transaction.objects.create(
                    tx_type='node_payout',
                    node_wallet=wallet,
                    amount=total_reward,
                    description=f"Reward: Storage {stored_bytes}B (Rep: {node.reputation_score}), Retrievals: {node.successful_retrievals}"
                )
            
            # Reset daily retrieval counters post-payout
            if node.successful_retrievals > 0 or node.failed_retrievals > 0:
                node.successful_retrievals = 0
                node.failed_retrievals = 0
                node.save(update_fields=['successful_retrievals', 'failed_retrievals'])
                
            logger.debug(f"Rewarded node {node.node_id} {total_reward} ATK for {stored_bytes} bytes and service.")
