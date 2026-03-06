from rest_framework.views import APIView
from apps.core.merkle import MerkleDAG
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from apps.storage.models import AccessLog
from rest_framework import status, permissions
from rest_framework.decorators import action
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Q, Sum, Max, Min
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from apps.core.crypto import ClientEncryption
import io
import logging
import hashlib
from datetime import timedelta
import base64

logger = logging.getLogger(__name__)


@method_decorator([csrf_exempt], name='dispatch')
class UploadView(APIView):
    """Handle file uploads with encryption and Merkle DAG"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, bucket_name):
        from apps.storage.models import Bucket, StorageQuota, AccessLog
        from workers.encoder import process_upload
        
        try:
            owner_did = getattr(request.user, 'did', str(request.user))
            
            bucket, created = Bucket.objects.get_or_create(
                name=bucket_name,
                defaults={'owner_did': owner_did}
            )
            
            if created:
                logger.info(f"Created new bucket '{bucket_name}' for {owner_did}")
            
            file_obj = request.FILES.get('file')
            if not file_obj:
                return Response({'error': 'No file provided', 'code': 'NO_FILE'}, status=400)
            
            if file_obj.size == 0:
                return Response({'error': 'Empty file not allowed', 'code': 'EMPTY_FILE'}, status=400)
            
            quota, _ = StorageQuota.objects.get_or_create(
                owner_did=owner_did,
                defaults={'quota_bytes': 10737418240}
            )
            
            if not quota.check_quota(file_obj.size):
                logger.warning(f"Quota exceeded for {owner_did}")
                return Response({
                    'error': 'Storage quota exceeded',
                    'code': 'QUOTA_EXCEEDED',
                    'used': quota.used_bytes,
                    'quota': quota.quota_bytes
                }, status=403)
            
            data = file_obj.read()
            file_hash = hashlib.sha256(data).hexdigest()
            
            import base64
            # Encode raw bytes to base64 string because Celery uses JSON serialization
            data_b64 = base64.b64encode(data).decode('utf-8')
            
            task = process_upload.delay(
                object_id=None,
                data_bytes=data_b64,
                mime_type=file_obj.content_type or 'application/octet-stream',
                bucket_id=str(bucket.id),
                owner_did=owner_did,
                filename=file_obj.name
            )
            
            AccessLog.objects.create(
                object=None,
                user_did=owner_did,
                action='upload',
                bytes_transferred=len(data),
                ip_address=request.META.get('REMOTE_ADDR'),
                status_code=202
            )
            
            logger.info(f"Upload queued: {file_obj.name} ({len(data)} bytes) -> {bucket_name}")
            
            return Response({
                'task_id': task.id,
                'status': 'processing',
                'size': len(data),
                'bucket': bucket_name,
                'mime_type': file_obj.content_type,
                'filename': file_obj.name,
                'hash': file_hash,
                'message': 'Upload queued for processing'
            }, status=202)
            
        except Exception as e:
            logger.error(f"Upload error: {e}", exc_info=True)
            return Response({'error': str(e), 'code': 'UPLOAD_ERROR'}, status=500)


@method_decorator([csrf_exempt], name='dispatch')
class PresignedDownloadView(APIView):
    """Download using presigned URL (no auth required)"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, token):
        from apps.storage.models import StorageObject, StorageNode
        from apps.storage.services import PresignedURLService
        from apps.storage.engine import get_erasure_engine
        import httpx
        import io
        
        try:
            payload = PresignedURLService.validate(token)
            obj = StorageObject.objects.get(id=payload['obj'], is_deleted=False)
            
            engine = get_erasure_engine()
            shards_dict = {}
            
            with httpx.Client(timeout=30.0) as client:
                for node_id, shard_index in obj.shard_map.items():
                    try:
                        node = StorageNode.objects.get(node_id=node_id, is_active=True)
                        resp = client.get(f"{node.endpoint}/shard/{obj.content_hash}/{shard_index}")
                        if resp.status_code == 200:
                            shards_dict[shard_index] = resp.content
                    except Exception as e:
                        logger.warning(f"Failed to fetch shard from {node_id}: {e}")
            
            if not shards_dict:
                raise Exception("No shards could be fetched")
            
            max_index = max(shards_dict.keys())
            shards_list = [shards_dict.get(i, None) for i in range(max_index + 1)]
            data = engine.decode(shards_list)
            
            response = StreamingHttpResponse(
                io.BytesIO(data),
                content_type=obj.mime_type
            )
            response['Content-Length'] = str(len(data))
            response['Content-Disposition'] = f'attachment; filename="{obj.id}"'
            
            AccessLog.objects.create(
                object=obj,
                user_did=payload.get('did', 'presigned'),
                action='presigned_download',
                bytes_transferred=len(data),
                ip_address=request.META.get('REMOTE_ADDR'),
                status_code=200
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Presigned download error: {e}", exc_info=True)
            return Response(
                {'error': str(e), 'code': 'PRESIGNED_ERROR'},
                status=status.HTTP_400_BAD_REQUEST
            )


@method_decorator([csrf_exempt], name='dispatch')
class ObjectDetailView(APIView):
    """Get object metadata and management"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, object_id):
        from apps.storage.models import EncryptedObject
        # Temporarily use basic serialization since we haven't updated serializers.py for EncryptedObject yet
        try:
            obj = EncryptedObject.objects.get(id=object_id, is_deleted=False)
            owner_did = getattr(request.user, 'did', str(request.user))
            
            if obj.owner_did != owner_did and not request.user.is_staff:
                return Response(
                    {'error': 'Access denied', 'code': 'ACCESS_DENIED'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            return Response({
                'id': str(obj.id),
                'content_hash': obj.original_hash,
                'bucket': obj.bucket.name if obj.bucket else None,
                'mime_type': obj.mime_type,
                'size': obj.original_size,
                'filename': obj.filename,
                'encrypted': True,
                'chunks': obj.chunk_count,
                'created_at': obj.created_at.isoformat(),
                'updated_at': obj.updated_at.isoformat()
            })
            
        except EncryptedObject.DoesNotExist:
            return Response(
                {'error': 'Object not found', 'code': 'NOT_FOUND'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, object_id):
        from apps.storage.models import EncryptedObject
        from workers.garbage_collector import process_garbage_collection
        from django.utils import timezone
        
        try:
            obj = EncryptedObject.objects.get(id=object_id, is_deleted=False)
            owner_did = getattr(request.user, 'did', str(request.user))
            
            if obj.owner_did != owner_did and not request.user.is_staff:
                return Response(
                    {'error': 'Access denied', 'code': 'ACCESS_DENIED'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            obj.is_deleted = True
            obj.deleted_at = timezone.now()
            obj.save()
            
            logger.info(f"Object {object_id} soft-deleted by {owner_did}")
            
            # Fire and forget background deletion of chunks across the network
            process_garbage_collection.delay(str(obj.id))
            
            return Response(
                {'status': 'deleted', 'object_id': str(obj.id), 'message': 'Object queued for network deletion'},
                status=status.HTTP_202_ACCEPTED
            )
            
        except EncryptedObject.DoesNotExist:
            return Response(
                {'error': 'Object not found', 'code': 'NOT_FOUND'},
                status=status.HTTP_404_NOT_FOUND
            )



@method_decorator([csrf_exempt], name='dispatch')
class ObjectListView(APIView):
    """List objects with filtering and pagination"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from apps.storage.models import EncryptedObject  # Changed from StorageObject
        
        try:
            owner_did = getattr(request.user, 'did', str(request.user))
            
            # Query EncryptedObject instead of StorageObject
            queryset = EncryptedObject.objects.filter(
                is_deleted=False,
                owner_did=owner_did
            ).select_related('bucket')
            
            bucket = request.query_params.get('bucket')
            if bucket:
                queryset = queryset.filter(bucket__name=bucket)
            
            mime_type = request.query_params.get('mime_type')
            if mime_type:
                queryset = queryset.filter(mime_type__startswith=mime_type)
            
            search = request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(original_hash__icontains=search) |
                    Q(mime_type__icontains=search) |
                    Q(filename__icontains=search)
                )
            
            sort = request.query_params.get('sort', '-created_at')
            queryset = queryset.order_by(sort)
            
            page = request.query_params.get('page', 1)
            page_size = request.query_params.get('page_size', 20)
            
            try:
                page = int(page)
                page_size = int(page_size)
            except (ValueError, TypeError):
                page = 1
                page_size = 20
            
            paginator = Paginator(queryset, page_size)
            
            try:
                page_obj = paginator.get_page(page)
            except PageNotAnInteger:
                page_obj = paginator.get_page(1)
            except EmptyPage:
                page_obj = paginator.get_page(paginator.num_pages)
            
            total_size = queryset.aggregate(total=Sum('original_size'))['total'] or 0
            
            return Response({
                'objects': [
                    {
                        'id': obj.id,
                        'content_hash': obj.original_hash,  # Changed from content_hash
                        'bucket': obj.bucket.name if obj.bucket else None,
                        'mime_type': obj.mime_type,
                        'size': obj.original_size,  # Changed from size
                        'filename': obj.filename,
                        'encrypted': True,
                        'chunks': obj.chunk_count,
                        'created_at': obj.created_at.isoformat(),
                        'updated_at': obj.updated_at.isoformat()
                    }
                    for obj in page_obj.object_list
                ],
                'pagination': {
                    'page': page_obj.number,
                    'page_size': page_size,
                    'total_pages': paginator.num_pages,
                    'total_objects': paginator.count,
                    'total_size_bytes': total_size,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                }
            })
            
        except Exception as e:
            logger.error(f"List objects error: {e}", exc_info=True)
            return Response(
                {'error': str(e), 'code': 'LIST_ERROR'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator([csrf_exempt], name='dispatch')
class PresignedURLView(APIView):
    """Generate presigned download URL"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, object_id):
        from apps.storage.models import StorageObject
        from apps.storage.services import PresignedURLService
        
        try:
            obj = StorageObject.objects.get(id=object_id, is_deleted=False)
            owner_did = getattr(request.user, 'did', str(request.user))
            
            if obj.owner_did != owner_did and not request.user.is_staff:
                return Response(
                    {'error': 'Access denied', 'code': 'ACCESS_DENIED'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            ttl = request.data.get('ttl', 3600)
            
            if ttl < 60 or ttl > 604800:
                return Response(
                    {'error': 'TTL must be between 60 and 604800 seconds', 'code': 'INVALID_TTL'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            url = PresignedURLService.generate(obj.id, owner_did, ttl=ttl)
            
            logger.info(f"Presigned URL generated for object {object_id} (TTL: {ttl}s)")
            
            return Response({
                'url': url,
                'expires_in': ttl,
                'expires_at': (timezone.now() + timedelta(seconds=ttl)).isoformat(),
                'object_id': str(obj.id),
                'size': obj.size
            })
            
        except StorageObject.DoesNotExist:
            return Response(
                {'error': 'Object not found', 'code': 'NOT_FOUND'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Presigned URL error: {e}", exc_info=True)
            return Response(
                {'error': str(e), 'code': 'PRESIGNED_ERROR'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator([csrf_exempt], name='dispatch')
class ObjectSearchView(APIView):
    """Search objects by various criteria"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from apps.storage.models import StorageObject
        
        try:
            owner_did = getattr(request.user, 'did', str(request.user))
            
            queryset = StorageObject.objects.filter(
                is_deleted=False,
                owner_did=owner_did
            ).select_related('bucket')
            
            query = request.query_params.get('q')
            if query:
                queryset = queryset.filter(
                    Q(content_hash__icontains=query) |
                    Q(mime_type__icontains=query) |
                    Q(bucket__name__icontains=query)
                )
            
            min_size = request.query_params.get('min_size')
            max_size = request.query_params.get('max_size')
            if min_size:
                queryset = queryset.filter(size__gte=int(min_size))
            if max_size:
                queryset = queryset.filter(size__lte=int(max_size))
            
            limit = min(int(request.query_params.get('limit', 50)), 100)
            queryset = queryset[:limit]
            
            results = [
                {
                    'id': obj.id,
                    'content_hash': obj.content_hash[:16] + '...',
                    'bucket': obj.bucket.name if obj.bucket else None,
                    'mime_type': obj.mime_type,
                    'size': obj.size,
                    'created_at': obj.created_at.isoformat()
                }
                for obj in queryset
            ]
            
            return Response({
                'count': len(results),
                'results': results
            })
            
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            return Response(
                {'error': str(e), 'code': 'SEARCH_ERROR'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BucketViewSet(ModelViewSet):
    """CRUD operations for Buckets"""
    from apps.storage.serializers import BucketSerializer
    serializer_class = BucketSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        from apps.storage.models import Bucket
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            return Bucket.objects.filter(owner_did=self.request.user.did)
        return Bucket.objects.none()
    
    def perform_create(self, serializer):
        if hasattr(self.request, 'user'):
            serializer.save(owner_did=self.request.user.did)
            logger.info(f"Bucket created: {serializer.instance.name}")
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get bucket statistics"""
        from apps.storage.models import Bucket, StorageObject
        from django.db.models import Sum, Count, Avg
        
        bucket = self.get_object()
        
        stats = StorageObject.objects.filter(
            bucket=bucket,
            is_deleted=False
        ).aggregate(
            total_objects=Count('id'),
            total_size=Sum('size'),
            avg_size=Avg('size'),
            min_size=Min('size'),
            max_size=Max('size')
        )
        
        recent_uploads = StorageObject.objects.filter(
            bucket=bucket,
            is_deleted=False,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        return Response({
            'bucket': bucket.name,
            'bucket_id': str(bucket.id),
            'owner_did': bucket.owner_did,
            'created_at': bucket.created_at.isoformat(),
            'statistics': {
                'total_objects': stats['total_objects'] or 0,
                'total_size': stats['total_size'] or 0,
                'average_size': stats['avg_size'] or 0,
                'min_size': stats['min_size'] or 0,
                'max_size': stats['max_size'] or 0
            },
            'activity': {
                'recent_uploads_7d': recent_uploads
            }
        })
    
    @action(detail=True, methods=['get'])
    def objects(self, request, pk=None):
        """List objects in bucket"""
        from apps.storage.models import StorageObject
        
        bucket = self.get_object()
        objects = StorageObject.objects.filter(
            bucket=bucket,
            is_deleted=False
        ).order_by('-created_at')[:100]
        
        return Response({
            'bucket': bucket.name,
            'objects': [
                {
                    'id': obj.id,
                    'content_hash': obj.content_hash,
                    'size': obj.size,
                    'mime_type': obj.mime_type,
                    'created_at': obj.created_at.isoformat()
                }
                for obj in objects
            ]
        })


class StorageNodeViewSet(ModelViewSet):
    """Manage storage nodes (admin only)"""
    from apps.storage.serializers import StorageNodeSerializer
    serializer_class = StorageNodeSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        from apps.storage.models import StorageNode
        return StorageNode.objects.all()
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get only active nodes"""
        from apps.storage.models import StorageNode
        nodes = StorageNode.objects.filter(is_active=True)
        serializer = self.get_serializer(nodes, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def health(self, request):
        """Check health of all nodes"""
        from apps.storage.models import StorageNode
        import httpx
        
        nodes = StorageNode.objects.all()
        health_status = []
        
        with httpx.Client(timeout=5.0) as client:
            for node in nodes:
                try:
                    resp = client.get(f"{node.endpoint}/health")
                    status_data = {
                        'node_id': node.node_id,
                        'endpoint': node.endpoint,
                        'is_active': node.is_active,
                        'health': resp.json() if resp.status_code == 200 else {'status': 'error'},
                        'response_time_ms': resp.elapsed.total_seconds() * 1000
                    }
                except Exception as e:
                    status_data = {
                        'node_id': node.node_id,
                        'endpoint': node.endpoint,
                        'is_active': node.is_active,
                        'health': {'status': 'unreachable', 'error': str(e)},
                        'response_time_ms': None
                    }
                
                health_status.append(status_data)
        
        return Response({
            'total_nodes': len(nodes),
            'active_nodes': sum(1 for n in nodes if n.is_active),
            'healthy_nodes': sum(1 for s in health_status if s['health'].get('status') == 'healthy'),
            'nodes': health_status
        })


class HealthView(APIView):
    """Health check endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        from django.db import connection
        
        health = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0',
            'checks': {}
        }
        
        try:
            connection.ensure_connection()
            health['checks']['database'] = 'ok'
        except Exception as e:
            health['checks']['database'] = f'error: {str(e)}'
            health['status'] = 'unhealthy'
        
        try:
            cache.set('health_check', 'ok', timeout=10)
            health['checks']['redis'] = 'ok'
        except Exception as e:
            health['checks']['redis'] = f'error: {str(e)}'
            health['status'] = 'unhealthy'
        
        try:
            from apps.storage.models import StorageNode
            active_nodes = StorageNode.objects.filter(is_active=True).count()
            health['checks']['storage_nodes'] = f'{active_nodes} active'
        except Exception as e:
            health['checks']['storage_nodes'] = f'error: {str(e)}'
        
        return Response(health)


class MetricsView(APIView):
    """Prometheus-style metrics endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        from apps.storage.models import StorageObject, StorageNode, AccessLog, Bucket
        from django.db.models import Sum
        
        metrics = []
        
        obj_count = StorageObject.objects.filter(is_deleted=False).count()
        metrics.append(f'aether_objects_total {obj_count}')
        
        node_count = StorageNode.objects.filter(is_active=True).count()
        metrics.append(f'aether_nodes_active {node_count}')
        
        total_bytes = StorageObject.objects.filter(is_deleted=False).aggregate(total=Sum('size'))['total'] or 0
        metrics.append(f'aether_storage_bytes {total_bytes}')
        
        bucket_count = Bucket.objects.count()
        metrics.append(f'aether_buckets_total {bucket_count}')
        
        download_count = AccessLog.objects.filter(action='download').count()
        metrics.append(f'aether_downloads_total {download_count}')
        
        upload_count = AccessLog.objects.filter(action='upload').count()
        metrics.append(f'aether_uploads_total {upload_count}')
        
        hour_ago = timezone.now() - timedelta(hours=1)
        recent_uploads = AccessLog.objects.filter(action='upload', timestamp__gte=hour_ago).count()
        metrics.append(f'aether_uploads_last_hour {recent_uploads}')
        
        recent_downloads = AccessLog.objects.filter(action='download', timestamp__gte=hour_ago).count()
        metrics.append(f'aether_downloads_last_hour {recent_downloads}')
        
        return Response('\n'.join(metrics), content_type='text/plain')


class StatsView(APIView):
    """System statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from apps.storage.models import StorageObject, StorageNode, AccessLog, Bucket
        from django.db.models import Sum
        
        owner_did = getattr(request.user, 'did', str(request.user))
        
        user_objects = StorageObject.objects.filter(owner_did=owner_did, is_deleted=False)
        user_total_size = user_objects.aggregate(total=Sum('size'))['total'] or 0
        
        system_total_size = StorageObject.objects.filter(is_deleted=False).aggregate(total=Sum('size'))['total'] or 0
        
        day_ago = timezone.now() - timedelta(days=1)
        week_ago = timezone.now() - timedelta(weeks=1)
        
        stats = {
            'user': {
                'did': owner_did,
                'total_objects': user_objects.count(),
                'total_size': user_total_size,
                'total_size_human': self._human_readable_size(user_total_size),
                'buckets': Bucket.objects.filter(owner_did=owner_did).count()
            },
            'system': {
                'total_objects': StorageObject.objects.filter(is_deleted=False).count(),
                'total_size': system_total_size,
                'total_size_human': self._human_readable_size(system_total_size),
                'active_nodes': StorageNode.objects.filter(is_active=True).count(),
                'total_buckets': Bucket.objects.count()
            },
            'activity': {
                'total_downloads': AccessLog.objects.filter(action='download').count(),
                'total_uploads': AccessLog.objects.filter(action='upload').count(),
                'downloads_24h': AccessLog.objects.filter(action='download', timestamp__gte=day_ago).count(),
                'uploads_24h': AccessLog.objects.filter(action='upload', timestamp__gte=day_ago).count(),
                'downloads_7d': AccessLog.objects.filter(action='download', timestamp__gte=week_ago).count(),
                'uploads_7d': AccessLog.objects.filter(action='upload', timestamp__gte=week_ago).count()
            }
        }
        
        return Response(stats)
    
    def _human_readable_size(self, size_bytes):
        """Convert bytes to human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.2f} {units[unit_index]}"
    
@method_decorator([csrf_exempt], name='dispatch')
class DownloadView(APIView):
    """Handle encrypted file downloads with Merkle verification"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, object_id):
        from apps.storage.models import EncryptedObject
        from workers.decoder import process_download
        
        try:
            obj = EncryptedObject.objects.get(id=object_id, is_deleted=False)
            owner_did = getattr(request.user, 'did', str(request.user))
            
            # Check ownership
            if obj.owner_did != owner_did and not request.user.is_staff:
                logger.warning(f"Access denied for {owner_did} on object {object_id}")
                return Response({'error': 'Access denied', 'code': 'ACCESS_DENIED'}, status=403)
            
            logger.info(f"Async download triggered for object {object_id}")
            
            # Dispatch Celery task
            task = process_download.delay(str(obj.id), owner_did)
            
            return Response({
                'task_id': task.id,
                'status': 'processing',
                'file_size': obj.original_size,
                'filename': obj.filename or str(obj.id),
                'message': 'Download queued for background reassembly and decryption'
            }, status=202)
            
        except EncryptedObject.DoesNotExist:
            logger.warning(f"Object {object_id} not found")
            return Response({'error': 'Object not found', 'code': 'NOT_FOUND'}, status=404)
        except Exception as e:
            logger.error(f"Download error: {e}", exc_info=True)
            return Response({'error': str(e), 'code': 'DOWNLOAD_ERROR'}, status=500)

class DownloadStatusView(APIView):
    """Check status of a background download task"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, task_id):
        from celery.result import AsyncResult
        
        task = AsyncResult(task_id)
        response_data = {'task_id': task_id, 'status': task.status.lower()}
        
        if task.successful():
            result = task.result
            if isinstance(result, dict):
                response_data.update(result)
        elif task.failed():
            response_data['error'] = str(task.result)
            
        return Response(response_data)

class DownloadFileView(APIView):
    """Stream the completely decrypted file to the client"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, task_id):
        from celery.result import AsyncResult
        from django.http import FileResponse
        import os
        
        task = AsyncResult(task_id)
        if not task.successful():
            return Response({'error': 'Task not completed', 'code': 'NOT_READY'}, status=400)
            
        result = task.result
        if not isinstance(result, dict) or 'output_path' not in result:
            return Response({'error': 'Invalid task result', 'code': 'INVALID_RESULT'}, status=500)
            
        file_path = result['output_path']
        if not os.path.exists(file_path):
            return Response({'error': 'File not found on disk', 'code': 'FILE_NOT_FOUND'}, status=404)
            
        try:
            # FileResponse automatically streams and closes the file pointer
            response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=result.get('filename', task_id))
            
            # Log access
            from apps.storage.models import AccessLog
            owner_did = getattr(request.user, 'did', str(request.user))
            AccessLog.objects.create(
                object=None,
                user_did=owner_did,
                action='download',
                bytes_transferred=result.get('size', 0),
                ip_address=request.META.get('REMOTE_ADDR'),
                status_code=200
            )
            
            return response
            
        except Exception as e:
            logger.error(f"File serving error: {e}")
            return Response({'error': 'Failed to serve file', 'code': 'SERVE_ERROR'}, status=500)


@method_decorator([csrf_exempt], name='dispatch')
class StreamFileView(APIView):
    """Dynamically streams file directly from P2P swarm, supporting HTTP Range requests"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, object_id):
        from apps.storage.models import EncryptedObject, StorageNode, AccessLog
        from apps.storage.engine import get_erasure_engine
        from apps.core.merkle import MerkleDAG
        from apps.core.crypto import ClientEncryption
        from django.http import StreamingHttpResponse, HttpResponse
        import httpx
        import base64
        import re
        
        try:
            owner_did = getattr(request.user, 'did', str(request.user))
            obj = EncryptedObject.objects.get(id=object_id, is_deleted=False)
            
            if obj.owner_did != owner_did:
                return Response({'error': 'Access denied'}, status=403)
                
            merkle_dag = MerkleDAG.from_dict(obj.merkle_dag)
            total_size = merkle_dag.total_size
            chunk_size = merkle_dag.chunk_size
            
            # Parse Range header
            range_header = request.META.get('HTTP_RANGE', '').strip()
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            
            start_byte = 0
            end_byte = total_size - 1
            
            if range_match:
                start_byte = int(range_match.group(1))
                if range_match.group(2):
                    end_byte = int(range_match.group(2))
                    
            if start_byte >= total_size:
                return HttpResponse(status=416) # Range Not Satisfiable
                
            end_byte = min(end_byte, total_size - 1)
            content_length = end_byte - start_byte + 1
            
            # Determine which chunks to pull
            start_chunk = start_byte // chunk_size
            end_chunk = end_byte // chunk_size
            
            metadata = obj.merkle_dag.get('metadata', {}) or {}
            strategy = metadata.get('encryption_strategy', 'legacy')
            
            if strategy == 'legacy':
                return Response({'error': 'Instant seeking is not mathematically possible for legacy whole-file encryption. Use standard download.'}, status=400)
                
            salt_b64 = metadata.get('salt')
            salt = base64.b64decode(salt_b64)
            encryption = ClientEncryption(password=f'{owner_did}:{salt.hex()}', salt=salt)
            engine = get_erasure_engine()
            
            def stream_generator():
                bytes_yielded = 0
                max_bytes = content_length
                current_byte_pos = start_byte
                
                with httpx.Client(timeout=30.0) as client:
                    for chunk_index in range(start_chunk, end_chunk + 1):
                        chunk_shards = {}
                        for key, node_id in obj.shard_map.items():
                            stored_chunk_idx, stored_shard_idx = map(int, key.split(':'))
                            if stored_chunk_idx == chunk_index:
                                try:
                                    node = StorageNode.objects.get(node_id=node_id, is_active=True)
                                    resp = client.get(f"{node.endpoint}/shard/{obj.root_hash}/{chunk_index}/{stored_shard_idx}")
                                    if resp.status_code == 200:
                                        chunk_shards[stored_shard_idx] = resp.content
                                except Exception:
                                    pass
                                    
                        if len(chunk_shards) < engine.data_shards:
                             break  # Stream will abort early if data unavailable
                             
                        shard_list = [chunk_shards.get(i, None) for i in range(max(chunk_shards.keys()) + 1)]
                        padded_encrypted_chunk = engine.decode(shard_list)
                        
                        chunk_meta = merkle_dag.chunks[chunk_index]
                        encrypted_chunk_size = chunk_meta.size + 28
                        encrypted_chunk = padded_encrypted_chunk[:encrypted_chunk_size]
                        
                        encrypted_package = {
                            'encrypted_data': base64.b64encode(encrypted_chunk).decode('utf-8'),
                            'salt': salt_b64
                        }
                        
                        try:
                            plaintext_chunk = encryption.decrypt(encrypted_package)
                        except Exception:
                            break
                            
                        # Slice the plaintext based on what we need
                        chunk_start_byte = chunk_index * chunk_size
                        slice_start = max(0, current_byte_pos - chunk_start_byte)
                        remaining_bytes_needed = max_bytes - bytes_yielded
                        slice_end = min(len(plaintext_chunk), slice_start + remaining_bytes_needed)
                        
                        chunk_to_yield = plaintext_chunk[slice_start:slice_end]
                        yield chunk_to_yield
                        
                        bytes_yielded += len(chunk_to_yield)
                        current_byte_pos += len(chunk_to_yield)
                        
                        if bytes_yielded >= max_bytes:
                            break
            
            response = StreamingHttpResponse(stream_generator(), status=206 if range_header else 200, content_type=obj.mime_type)
            response['Content-Length'] = str(content_length)
            response['Accept-Ranges'] = 'bytes'
            if range_header:
                response['Content-Range'] = f'bytes {start_byte}-{end_byte}/{total_size}'
                
            return response
            
        except EncryptedObject.DoesNotExist:
            return Response({'error': 'Object not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)