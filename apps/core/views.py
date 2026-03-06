from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection
from django.core.cache import cache
from apps.storage.models import StorageObject, StorageNode
from celery import current_app
import psutil
import os

class HealthCheckView(APIView):
    """Comprehensive health check endpoint"""
    authentication_classes = []
    permission_classes = []
    
    def get(self, request):
        health = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'checks': {}
        }
        
        # Database check
        try:
            connection.ensure_connection()
            health['checks']['database'] = 'ok'
        except Exception as e:
            health['checks']['database'] = f'error: {str(e)}'
            health['status'] = 'unhealthy'
        
        # Redis check
        try:
            cache.set('health_check', 'ok', timeout=10)
            health['checks']['redis'] = 'ok'
        except Exception as e:
            health['checks']['redis'] = f'error: {str(e)}'
            health['status'] = 'unhealthy'
        
        # Celery check
        try:
            inspect = current_app.control.inspect()
            active = inspect.active()
            health['checks']['celery'] = 'ok' if active else 'no workers'
        except Exception as e:
            health['checks']['celery'] = f'error: {str(e)}'
        
        # Storage nodes check
        active_nodes = StorageNode.objects.filter(is_active=True).count()
        health['checks']['storage_nodes'] = f'{active_nodes} active'
        
        # System resources
        health['checks']['cpu'] = f'{psutil.cpu_percent()}%'
        health['checks']['memory'] = f'{psutil.virtual_memory().percent}%'
        health['checks']['disk'] = f'{psutil.disk_usage("/").percent}%'
        
        status_code = 200 if health['status'] == 'healthy' else 503
        return Response(health, status=status_code)

class MetricsView(APIView):
    """Prometheus-style metrics endpoint"""
    authentication_classes = []
    
    def get(self, request):
        metrics = []
        
        # Object count
        obj_count = StorageObject.objects.filter(is_deleted=False).count()
        metrics.append(f'aether_objects_total {obj_count}')
        
        # Storage nodes
        node_count = StorageNode.objects.filter(is_active=True).count()
        metrics.append(f'aether_nodes_active {node_count}')
        
        # Total storage
        total_bytes = StorageObject.objects.filter(
            is_deleted=False
        ).aggregate(total=models.Sum('size'))['total'] or 0
        metrics.append(f'aether_storage_bytes {total_bytes}')
        
        # Celery queue length
        try:
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            if stats:
                for worker, data in stats.items():
                    metrics.append(f'aether_celery_worker_up{{worker="{worker}"}} 1')
        except:
            pass
        
        return Response(
            '\n'.join(metrics),
            content_type='text/plain'
        )