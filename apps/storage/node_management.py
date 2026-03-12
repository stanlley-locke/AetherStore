from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.db import models, transaction
from django.db.models import Sum, Count, Avg
from decimal import Decimal
from apps.storage.models import StorageNode, MiningReward
from apps.billing.models import UserWallet, NodeWallet, Transaction
import logging

logger = logging.getLogger(__name__)

def _owner_did(request):
    return getattr(request.user, 'did', str(request.user))


class NodeClaimView(APIView):
    """Link a headless storage node to a user's wallet (Phase 29)"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        node_id = request.data.get('node_id')
        if not node_id:
            return Response({'error': 'node_id is required'}, status=400)

        try:
            node = StorageNode.objects.get(node_id=node_id)
            if node.owner_did:
                if node.owner_did == _owner_did(request):
                    return Response({'message': 'Node already claimed by you', 'node_id': node_id}, status=200)
                return Response({'error': 'Node already claimed by another user'}, status=403)
            
            node.owner_did = _owner_did(request)
            node.save()
            return Response({
                'message': 'Node claimed successfully',
                'node_id': node_id,
                'owner_did': node.owner_did
            }, status=200)
        except StorageNode.DoesNotExist:
            # For prototype, we'll auto-create it if it doesn't exist but has a valid ID
            endpoint = request.data.get('endpoint', 'http://localhost:8001')
            node = StorageNode.objects.create(
                node_id=node_id,
                endpoint=endpoint,
                owner_did=_owner_did(request),
                is_active=True
            )
            return Response({
                'message': 'New node registered and claimed',
                'node_id': node_id,
                'owner_did': node.owner_did
            }, status=201)

class MinerFleetView(APIView):
    """Get status and metrics for all nodes in a miner's fleet (Phase 29)"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.p2p.services.node_monitor import node_monitor
        did = _owner_did(request)
        nodes = StorageNode.objects.filter(owner_did=did)
        
        fleet_data = []
        total_capacity = 0
        total_used = 0
        
        for node in nodes:
            total_capacity += node.capacity_bytes
            total_used += node.used_bytes
            
            # Fetch real-time health if active
            health = node_monitor.check_node_health(node.node_id, node.endpoint)
            
            # Calculate actual uptime % based on reputation/heartbeats for now, 
            # or use the reported uptime if available
            reported_uptime = 99.9
            dht_peers = 0
            if health['healthy'] and health['stats']:
                dht_peers = health['stats'].get('dht_peers', 0)
                # If the node reports its own uptime, we could use it, 
                # but for the "Uptime %" we usually want a historical average.
                # For now, we'll keep the 99.9 placeholder or link it to is_active.
            
            fleet_data.append({
                'node_id': node.node_id,
                'endpoint': node.endpoint,
                'is_active': health['healthy'], # Update active status based on real probe
                'uptime_pct': node.reputation_score if node.reputation_score > 0 else 99.9,
                'used_bytes': node.used_bytes,
                'capacity_bytes': node.capacity_bytes,
                'reputation': node.reputation_score,
                'last_heartbeat': node.last_heartbeat,
                'latency_ms': health['latency_ms'],
                'dht_peers': dht_peers
            })

        return Response({
            'fleet_count': nodes.count(),
            'total_capacity_bytes': total_capacity,
            'total_used_bytes': total_used,
            'nodes': fleet_data
        })

class MinerEarningsView(APIView):
    """Financial analytics for mining operations (Phase 29)"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        did = _owner_did(request)
        nodes = StorageNode.objects.filter(owner_did=did)
        
        rewards = MiningReward.objects.filter(node__in=nodes)
        
        # Aggregate by type
        stats = rewards.aggregate(
            total_earned=Sum('amount'),
            avg_reward=Avg('amount'),
            reward_count=Count('id')
        )
        
        # Recent rewards
        recent = rewards.order_by('-timestamp')[:50]
        
        return Response({
            'total_earned': stats['total_earned'] or 0,
            'avg_reward': stats['avg_reward'] or 0,
            'reward_count': stats['reward_count'] or 0,
            'recent_history': [
                {
                    'node_id': r.node.node_id,
                    'amount': r.amount,
                    'type': r.reward_type,
                    'timestamp': r.timestamp
                } for r in recent
            ]
        })

class NodePayoutView(APIView):
    """Transfer earned ATK from nodes to user's main wallet (Phase 31)"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        did = _owner_did(request)
        nodes = StorageNode.objects.filter(owner_did=did)
        node_ids = nodes.values_list('node_id', flat=True)
        
        node_wallets = NodeWallet.objects.filter(node_id__in=node_ids, earned_balance__gt=0)
        if not node_wallets.exists():
            return Response({'error': 'No pending rewards to payout'}, status=400)

        total_payout = node_wallets.aggregate(total=Sum('earned_balance'))['total']
        
        try:
            with transaction.atomic():
                # Get or create user wallet
                user_wallet, _ = UserWallet.get_or_create_linked(did=did)
                
                # Perform the transfer
                user_wallet.balance += total_payout
                user_wallet.save()
                
                # Log transaction for user
                Transaction.objects.create(
                    tx_type='node_payout',
                    user_wallet=user_wallet,
                    amount=total_payout,
                    description=f"Consolidated payout from {node_wallets.count()} nodes."
                )
                
                # Reset node balances and log per-node transactions
                for nw in node_wallets:
                    payout_amount = nw.earned_balance
                    nw.earned_balance = Decimal('0.0')
                    nw.save()
                    
                    Transaction.objects.create(
                        tx_type='node_payout',
                        node_wallet=nw,
                        amount=-payout_amount, # Deduct from node wallet
                        description=f"Payout to user {did}"
                    )
                
            return Response({
                'message': 'Payout successful',
                'amount_paid': total_payout,
                'nodes_updated': node_wallets.count()
            }, status=200)

        except Exception as e:
            logger.error(f"Payout failed for {did}: {str(e)}")
            return Response({'error': 'Payout failed due to an internal error'}, status=500)

import requests

class NodeLogProxyView(APIView):
    """Proxy logs from a storage node's internal HTTP server to the portal dashboard"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, node_id):
        print(f"DEBUG: NodeLogProxyView hit for node_id: {node_id}")
        try:
            node = StorageNode.objects.get(node_id=node_id)
            print(f"DEBUG: Found node: {node.node_id}, endpoint: {node.endpoint}, owner: {node.owner_did}")
            
            # Only owner or network admin can see logs
            current_did = _owner_did(request)
            if node.owner_did != current_did and not getattr(request.user, 'is_network_admin', False):
                print(f"DEBUG: Access denied. Owner: {node.owner_did}, Current: {current_did}")
                return Response({'error': 'Access denied'}, status=403)
            
            lines = request.query_params.get('lines', '100')
            target_url = f"{node.endpoint.rstrip('/')}/logs?lines={lines}"
            print(f"DEBUG: Proxying request to: {target_url}")
            
            resp = requests.get(target_url, timeout=5.0)
            print(f"DEBUG: Node response status: {resp.status_code}")
            
            if resp.status_code == 200:
                return Response(resp.json())
            else:
                return Response({'error': f'Node returned {resp.status_code}'}, status=resp.status_code)
                    
        except StorageNode.DoesNotExist:
            print(f"DEBUG: Node {node_id} not found in DB")
            return Response({'error': 'Node not found'}, status=404)
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Request to node failed: {str(e)}")
            return Response({'error': f'Failed to reach node: {str(e)}'}, status=502)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"DEBUG: Unexpected error in NodeLogProxyView: {str(e)}")
            return Response({'error': str(e)}, status=500)
