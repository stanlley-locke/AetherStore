from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.db.models import Sum
from django.contrib.auth import get_user_model
from apps.storage.models import NetworkParameter, StorageNode, StorageQuota, EncryptedObject
from apps.billing.models import UserWallet, NodeWallet
from apps.accounts.permissions import IsNetworkAdmin
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class NetworkParameterView(APIView):
    """GET/PATCH core network parameters (Erasure Coding, Block Rewards)"""
    permission_classes = [IsNetworkAdmin]

    def get(self, request):
        params = NetworkParameter.objects.all()
        return Response({p.key: p.value for p in params})

    def patch(self, request):
        updated = []
        for key, value in request.data.items():
            param, _ = NetworkParameter.objects.update_or_create(
                key=key,
                defaults={'value': value, 'updated_by': getattr(request.user, 'did', str(request.user))}
            )
            updated.append(key)
        return Response({'message': 'Parameters updated', 'updated': updated})


class TreasuryAnalyticsView(APIView):
    """Global insights into ATK supply and storage consumption"""
    permission_classes = [IsNetworkAdmin]

    def get(self, request):
        user_balances = UserWallet.objects.aggregate(total=Sum('balance'))['total'] or 0
        node_earnings = NodeWallet.objects.aggregate(total=Sum('earned_balance'))['total'] or 0
        
        total_storage_used = StorageQuota.objects.aggregate(total=Sum('used_bytes'))['total'] or 0
        total_objects = EncryptedObject.objects.filter(is_deleted=False).count()
        
        active_nodes = StorageNode.objects.filter(is_active=True).count()
        
        return Response({
            'atk_circulating_supply': float(user_balances + node_earnings),
            'user_wallets_total': float(user_balances),
            'node_earnings_unclaimed': float(node_earnings),
            'global_storage_consumption_bytes': total_storage_used,
            'total_active_objects': total_objects,
            'active_network_nodes': active_nodes
        })


class UserQuotaManagementView(APIView):
    """Admin interface to adjust or revoke user storage quotas"""
    permission_classes = [IsNetworkAdmin]

    def get(self, request, did):
        try:
            quota = StorageQuota.objects.get(owner_did=did)
            return Response({
                'did': did,
                'quota_bytes': quota.quota_bytes,
                'used_bytes': quota.used_bytes,
                'last_calculated': quota.last_calculated
            })
        except StorageQuota.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)

    def post(self, request, did):
        new_quota = request.data.get('quota_bytes')
        if not new_quota:
            return Response({'error': 'quota_bytes is required'}, status=400)
            
        quota, created = StorageQuota.objects.get_or_create(
            owner_did=did,
            defaults={'quota_bytes': new_quota}
        )
        if not created:
            quota.quota_bytes = new_quota
            quota.save()
            
        return Response({
            'message': 'Quota updated',
            'did': did,
            'new_quota_bytes': new_quota
        })


class AdminUserManagementView(APIView):
    """List all users and toggle their network admin status"""
    permission_classes = [IsNetworkAdmin]

    def get(self, request):
        """List all registered users with their admin status"""
        users = User.objects.all().values('username', 'did', 'is_network_admin', 'date_joined', 'is_active')
        return Response({'users': list(users), 'total': User.objects.count()})

    def post(self, request):
        """Promote or demote a user to/from network admin by DID"""
        target_did = request.data.get('did')
        promote = request.data.get('is_network_admin', True)
        
        if not target_did:
            return Response({'error': 'did is required'}, status=400)
        
        try:
            user = User.objects.get(did=target_did)
        except User.DoesNotExist:
            return Response({'error': f'No user found with DID: {target_did}'}, status=404)
        
        # Prevent self-demotion
        if user == request.user and not promote:
            return Response({'error': 'Cannot remove your own admin privileges'}, status=400)
        
        user.is_network_admin = promote
        user.save(update_fields=['is_network_admin'])
        
        action = 'granted' if promote else 'revoked'
        logger.info(f"Admin status {action} for {target_did} by {getattr(request.user, 'did', request.user)}")
        return Response({
            'message': f'Network admin access {action} for {target_did}',
            'did': target_did,
            'is_network_admin': promote
        })


class AdminStatusView(APIView):
    """Check if the current authenticated user is a network admin"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            'did': getattr(request.user, 'did', None),
            'is_network_admin': getattr(request.user, 'is_network_admin', False),
            'username': request.user.username,
        })
