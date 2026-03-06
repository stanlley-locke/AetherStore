from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status


class NodeHealthView(APIView):
    """Check health of all storage nodes"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        from apps.p2p.services.node_monitor import node_monitor
        
        cluster_status = node_monitor.get_cluster_status()
        
        if cluster_status['cluster_healthy']:
            return Response(cluster_status, status=200)
        else:
            return Response(cluster_status, status=503)


class NodeActivateView(APIView):
    """Re-activate healthy nodes"""
    permission_classes = [permissions.IsAdminUser]
    
    def post(self, request):
        from apps.p2p.services.node_monitor import node_monitor
        
        node_monitor.activate_healthy_nodes()
        status = node_monitor.get_cluster_status()
        
        return Response({
            'message': 'Node health check completed',
            'status': status
        })
