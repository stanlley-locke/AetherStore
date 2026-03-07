from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from .models import UserWallet, NodeWallet, Transaction

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
