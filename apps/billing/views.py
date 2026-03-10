from django.db import models, transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from decimal import Decimal
import time
import hashlib
import logging
from .models import UserWallet, NodeWallet, Transaction, LedgerTransaction
from apps.core import crypto_wallet

logger = logging.getLogger(__name__)

@method_decorator([csrf_exempt], name='dispatch')
class WalletBalanceView(APIView):
    """View the current user's wallet balance and recent transactions."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        owner_did = getattr(request.user, 'did', str(request.user))
        wallet, created = UserWallet.objects.get_or_create(did=owner_did)
        
        # Get last 10 transactions
        transactions = Transaction.objects.filter(user_wallet=wallet)[:10]
        tx_data = [{
            'id': str(tx.id),
            'type': tx.tx_type,
            'amount': float(tx.amount),
            'description': tx.description,
            'date': tx.created_at.isoformat()
        } for tx in transactions]

        return Response({
            'did': wallet.did,
            'balance': float(wallet.balance),
            'recent_transactions': tx_data
        })


@method_decorator([csrf_exempt], name='dispatch')
class DepositFundsView(APIView):
    """
    Deposit funds into the user wallet.
    In a real system, this would be a webhook from Stripe/Crypto payment gateway.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        owner_did = getattr(request.user, 'did', str(request.user))
        amount = request.data.get('amount')
        
        if not amount:
            return Response({'error': 'amount is required'}, status=400)
            
        try:
            amount_decimal = Decimal(str(amount))
            if amount_decimal <= 0:
                raise ValueError
        except:
            return Response({'error': 'amount must be a positive number'}, status=400)

        wallet, _ = UserWallet.objects.get_or_create(did=owner_did)
        
        wallet.balance += amount_decimal
        wallet.save()
        
        Transaction.objects.create(
            tx_type='deposit',
            user_wallet=wallet,
            amount=amount_decimal,
            description=f"Deposit via payment gateway"
        )
        
        return Response({
            'status': 'success',
            'new_balance': float(wallet.balance),
            'deposited': float(amount_decimal)
        })


@method_decorator([csrf_exempt], name='dispatch')
class NodeEarningsView(APIView):
    """View a node's earnings and withdraw them. Node authenticates via its Node ID (simplified for now)."""
    
    def get(self, request, node_id):
        # In a real system, nodes would cryptographically sign requests to prove identity
        wallet, _ = NodeWallet.objects.get_or_create(node_id=node_id)
        
        transactions = Transaction.objects.filter(node_wallet=wallet)[:10]
        tx_data = [{
            'id': str(tx.id),
            'type': tx.tx_type,
            'amount': float(tx.amount),
            'description': tx.description,
            'date': tx.created_at.isoformat()
        } for tx in transactions]

        return Response({
            'node_id': wallet.node_id,
            'earned_balance': float(wallet.earned_balance),
            'recent_transactions': tx_data
        })
        
    def post(self, request, node_id):
        """Withdraw node earnings."""
        wallet, _ = NodeWallet.objects.get_or_create(node_id=node_id)
        amount = request.data.get('amount')
        
        if not amount:
            amount_decimal = wallet.earned_balance  # Withdraw all by default
        else:
            try:
                amount_decimal = Decimal(str(amount))
                if amount_decimal <= 0:
                    raise ValueError
            except:
                return Response({'error': 'amount must be a positive number'}, status=400)
                
        if amount_decimal > wallet.earned_balance:
            return Response({'error': 'insufficient earned balance'}, status=400)
            
        if amount_decimal > 0:
            wallet.earned_balance -= amount_decimal
            wallet.save()
            
            Transaction.objects.create(
                tx_type='withdrawal',
                node_wallet=wallet,
                amount=-amount_decimal,
                description=f"Earnings withdrawal"
            )
            
        return Response({
            'status': 'success',
            'withdrawn': float(amount_decimal),
            'remaining_balance': float(wallet.earned_balance)
        })

@method_decorator([csrf_exempt], name='dispatch')
class WalletCreateView(APIView):
    """
    Generates a new non-custodial wallet (BIP-39 Mnemonic + Ed25519 Keypair).
    Maps the resulting `ath1...` address to the authenticated user's DID.
    This endpoint does NOT store the private key or mnemonic on the server.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        owner_did = None
        if hasattr(request, 'user') and hasattr(request.user, 'did'):
            owner_did = request.user.did
        elif auth_header.startswith('DID-Signature '):
            parts = auth_header.replace('DID-Signature ', '').split(':')
            if len(parts) >= 3:
                owner_did = ':'.join(parts[:3])
                
        if not owner_did:
            owner_did = f"did:example:anon:{int(time.time())}"
        
        # 1. Generate core crypto keys non-custodially
        mnemonic = crypto_wallet.generate_mnemonic()
        wallet_data = crypto_wallet.derive_keypair(mnemonic)
        address = wallet_data['address']
        
        # 2. Migration Logic: Find existing record by address OR legacy DID
        stable_did = wallet_data['did']
        legacy_did = f"did:aether:{address[4:20]}"
        
        existing_wallet = UserWallet.objects.filter(
            models.Q(did=stable_did) | 
            models.Q(address=address) | 
            models.Q(did=legacy_did)
        ).first()
        
        if existing_wallet:
            if existing_wallet.did != stable_did:
                # Migrate to stable DID (delete old PK, create new)
                old_balance = existing_wallet.balance
                existing_wallet.delete()
                wallet = UserWallet.objects.create(
                    did=stable_did,
                    address=address,
                    balance=old_balance
                )
                logger.info(f"Migrated legacy wallet {existing_wallet.did} -> {stable_did}")
            else:
                # Just ensure address is set
                wallet = existing_wallet
                if wallet.address != address:
                    wallet.address = address
                    wallet.save(update_fields=['address'])
        else:
            # Brand new
            wallet = UserWallet.objects.create(
                did=stable_did,
                address=address,
                balance=Decimal('100.0')
            )
        
        return Response({
            'status': 'success',
            'message': 'Wallet generated successfully. Store your mnemonic safely; the server will drop this data immediately.',
            'address': address,
            'did': wallet.did,
            'public_key': wallet_data['public_key'],
            'private_key': wallet_data['private_key'],  # Only returned once!
            'mnemonic': wallet_data['mnemonic']
        })

class WalletRecoveryView(APIView):
    """
    Recovers a wallet from a BIP-39 mnemonic and binds it to the current user's DID.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        mnemonic = request.data.get('mnemonic')
        
        if not mnemonic:
            return Response({'error': 'Mnemonic is required.'}, status=400)
            
        try:
            # Re-derive keys from mnemonic
            wallet_data = crypto_wallet.derive_keypair(mnemonic)
            address = wallet_data['address']
            stable_did = wallet_data['did']
            
            # 2. Migration Logic: Find existing record by address OR legacy DID
            legacy_did = f"did:aether:{address[4:20]}"
            
            existing_wallet = UserWallet.objects.filter(
                models.Q(did=stable_did) | 
                models.Q(address=address) | 
                models.Q(did=legacy_did)
            ).first()
            
            if existing_wallet:
                if existing_wallet.did != stable_did:
                    # Migrate to stable DID
                    old_balance = existing_wallet.balance
                    existing_wallet.delete()
                    wallet = UserWallet.objects.create(
                        did=stable_did,
                        address=address,
                        balance=old_balance
                    )
                    logger.info(f"Migrated legacy wallet {existing_wallet.did} -> {stable_did} during recovery")
                else:
                    wallet = existing_wallet
                    if wallet.address != address:
                        wallet.address = address
                        wallet.save(update_fields=['address'])
            else:
                # Get or create (safety fallback)
                wallet, _ = UserWallet.objects.get_or_create(
                    did=stable_did,
                    defaults={'address': address, 'balance': Decimal('100.0')}
                )
                    
            return Response({
                'status': 'success',
                'message': 'Wallet recovered successfully.',
                'address': address,
                'did': wallet.did,
                'public_key': wallet_data['public_key'],
                'private_key': wallet_data['private_key']
            })
        except Exception as e:
            return Response({'error': f'Failed to recover wallet: {str(e)}'}, status=400)


class WalletResolveView(APIView):
    """
    Resolve a wallet address to a user DID.
    This is required for initiating communication using only an ATK wallet address.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, address):
        try:
            address = address.strip().lower()
            wallet = UserWallet.objects.filter(address=address).first()
            if not wallet:
                # Fallback to DID lookup
                wallet = UserWallet.objects.filter(did=address).first()
                if not wallet:
                    return Response({'error': 'Wallet address not found on the network.'}, status=404)
                
            return Response({
                'address': wallet.address,
                'did': wallet.did
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)


@method_decorator([csrf_exempt], name='dispatch')
class WalletTransferView(APIView):
    """
    Executes a P2P ATK coin transfer cryptographically signed by the sender.
    Payload expected: public_key, recipient_address, amount, timestamp, signature.
    Signature payload must be: f"{recipient_address}:{amount}:{timestamp}"
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        try:
            public_key = request.data.get('public_key')
            recipient_target = request.data.get('recipient_address', '').strip().lower()
            amount = request.data.get('amount')
            timestamp_str = request.data.get('timestamp')
            signature = request.data.get('signature')
            
            if not all([public_key, recipient_target, amount, timestamp_str, signature]):
                return Response({'error': 'Missing required fields for cryptographic transfer.'}, status=400)
                
            try:
                amount_decimal = Decimal(str(amount))
                fee = Decimal('0.001') # Standard network fee
                total_needed = amount_decimal + fee
                if amount_decimal <= 0:
                    raise ValueError
            except:
                return Response({'error': 'amount must be a positive number'}, status=400)
                
            # 1. Reconstruct message and verify signature
            # Use exact string value for amount from request to match frontend signing
            raw_amount = str(request.data.get('amount'))
            message_to_verify = f"{recipient_target}:{raw_amount}:{timestamp_str}"
            is_valid = crypto_wallet.verify_signature(public_key, message_to_verify, signature)
            
            if not is_valid:
                return Response({
                    'error': 'Invalid Ed25519 signature.',
                    'debug': {
                        'message_expected': message_to_verify,
                        'public_key': public_key
                    }
                }, status=403)
                
            # 2. Derive sender address from verified public key
            pub_bytes = bytes.fromhex(public_key)
            pub_hash = hashlib.sha256(pub_bytes).hexdigest()
            sender_address = f"ath1{pub_hash[:40]}".lower()
            
            # Generate TX Hash
            tx_payload = f"{sender_address}:{recipient_target}:{raw_amount}:{timestamp_str}:{signature}"
            tx_hash = hashlib.sha256(tx_payload.encode('utf-8')).hexdigest()
            
            if LedgerTransaction.objects.filter(tx_hash=tx_hash).exists():
                return Response({'error': 'Replay attack blocked. Transaction already executed.'}, status=409)
                
            # 3. Locate wallets and enforce ledger logic
            with transaction.atomic():
                # Find sender
                sender_wallet = UserWallet.objects.filter(
                    models.Q(address=sender_address) | models.Q(did=f"did:aether:{sender_address}")
                ).first()
                
                is_node_sender = False
                if not sender_wallet:
                    sender_wallet = NodeWallet.objects.filter(address=sender_address).first()
                    if sender_wallet:
                        is_node_sender = True
                    
                if not sender_wallet:
                    return Response({'error': f'Sender wallet ({sender_address}) not found.'}, status=404)
                    
                # Check balance
                available_balance = sender_wallet.earned_balance if is_node_sender else sender_wallet.balance
                if available_balance < total_needed:
                    return Response({'error': f'Insufficient funds. Need {total_needed} ATK (incl. 0.001 fee), have {available_balance}.'}, status=400)
                    
                # Find recipient (handle both direct address and DID)
                recipient_wallet = UserWallet.objects.filter(
                    models.Q(address=recipient_target) | models.Q(did=recipient_target)
                ).first()
                
                is_node_recipient = False
                if not recipient_wallet:
                    recipient_wallet = NodeWallet.objects.filter(
                        models.Q(address=recipient_target) | models.Q(node_id=recipient_target)
                    ).first()
                    if recipient_wallet:
                        is_node_recipient = True
                    
                if not recipient_wallet:
                    # If recipient doesn't exist AND target is an address, create pseudo wallet
                    if recipient_target.startswith('ath1'):
                        recipient_wallet = UserWallet.objects.create(
                            did=f"pending:{recipient_target}", 
                            address=recipient_target, 
                            balance=Decimal('0.0')
                        )
                    else:
                        return Response({'error': 'Recipient DID not found and no valid address provided.'}, status=404)
                
                recipient_address = recipient_wallet.address or recipient_target

                # 4. State Transitions
                if is_node_sender:
                    sender_wallet.earned_balance -= total_needed
                else:
                    sender_wallet.balance -= total_needed
                sender_wallet.save()
                
                if is_node_recipient:
                    recipient_wallet.earned_balance += amount_decimal
                else:
                    recipient_wallet.balance += amount_decimal
                recipient_wallet.save()
                
                # Record exactly in Ledger
                LedgerTransaction.objects.create(
                    tx_hash=tx_hash,
                    sender_address=sender_address,
                    recipient_address=recipient_address,
                    amount=amount_decimal,
                    signature=signature
                )
                
                # Create user-facing transaction history records
                if not is_node_sender:
                    Transaction.objects.create(
                        tx_type='transfer_out',
                        user_wallet=sender_wallet,
                        amount=-amount_decimal,
                        description=f"Sent ATK to {recipient_address[:8]}..."
                    )
                else:
                    Transaction.objects.create(
                        tx_type='transfer_out',
                        node_wallet=sender_wallet,
                        amount=-amount_decimal,
                        description=f"Sent ATK to {recipient_address[:8]}..."
                    )
                    
                if not is_node_recipient:
                    Transaction.objects.create(
                        tx_type='transfer_in',
                        user_wallet=recipient_wallet,
                        amount=amount_decimal,
                        description=f"Received ATK from {sender_address[:8]}..."
                    )
                else:
                    Transaction.objects.create(
                        tx_type='transfer_in',
                        node_wallet=recipient_wallet,
                        amount=amount_decimal,
                        description=f"Received ATK from {sender_address[:8]}..."
                    )
                    
            return Response({
                'status': 'success',
                'tx_hash': tx_hash,
                'message': 'Cryptographic transfer executed on the ledger.',
                'amount_transferred': float(amount_decimal),
                'fee_paid': float(fee)
            })
        except Exception as e:
            logger.error(f"Transfer error: {e}", exc_info=True)
            return Response({'error': str(e)}, status=500)


