from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BucketViewSet,
    StorageNodeViewSet,
    UploadView,
    DownloadView,
    PresignedDownloadView,
    ObjectDetailView,
    ObjectListView,
    PresignedURLView,
    HealthView,
    MetricsView,
    StatsView,
)

router = DefaultRouter()
router.register(r'buckets', BucketViewSet, basename='bucket')
router.register(r'nodes', StorageNodeViewSet, basename='node')

urlpatterns = [
    path('', include(router.urls)),
    
    # Upload/Download
    path('upload/<str:bucket_name>/', UploadView.as_view(), name='upload'),
    path('download/<uuid:object_id>/', DownloadView.as_view(), name='download'),
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
