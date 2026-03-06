from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BucketViewSet,
    StorageNodeViewSet,
    UploadView,
    DownloadView,
    DownloadStatusView,
    DownloadFileView,
    PresignedDownloadView,
    ObjectDetailView,
    ObjectListView,
    PresignedURLView,
    HealthView,
    MetricsView,
    StatsView,
    MultipartInitView,
    MultipartUploadPartView,
    MultipartCompleteView,
)

router = DefaultRouter()
router.register(r'buckets', BucketViewSet, basename='bucket')
router.register(r'nodes', StorageNodeViewSet, basename='node')

urlpatterns = [
    path('', include(router.urls)),
    
    # Upload/Download
    path('upload/<str:bucket_name>/', UploadView.as_view(), name='upload'),
    path('upload/multipart/init/', MultipartInitView.as_view(), name='multipart-init'),
    path('upload/multipart/<uuid:upload_id>/part/<int:part_number>/', MultipartUploadPartView.as_view(), name='multipart-part'),
    path('upload/multipart/<uuid:upload_id>/complete/', MultipartCompleteView.as_view(), name='multipart-complete'),
    
    path('download/<uuid:object_id>/', DownloadView.as_view(), name='download'),
    path('download/status/<str:task_id>/', DownloadStatusView.as_view(), name='download-status'),
    path('download/file/<str:task_id>/', DownloadFileView.as_view(), name='download-file'),
    path('download/presigned/<str:token>/', PresignedDownloadView.as_view(), name='presigned-download'),
    
    # Object management
    path('object/<uuid:object_id>/', ObjectDetailView.as_view(), name='object-detail'),
    path('objects/', ObjectListView.as_view(), name='object-list'),
    path('object/<uuid:object_id>/presigned/', PresignedURLView.as_view(), name='object-presigned'),
    
    # System endpoints
    path('health/', HealthView.as_view(), name='health'),
    path('metrics/', MetricsView.as_view(), name='metrics'),
    path('stats/', StatsView.as_view(), name='stats'),
]
