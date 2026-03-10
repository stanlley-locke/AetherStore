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
    ObjectVersionsView,
    NameRecordView,
    NameResolveView,
    PresignedURLView,
    HealthView,
    MetricsView,
    StatsView,
    MultipartInitView,
    MultipartUploadPartView,
    MultipartCompleteView,
    StreamFileView,
    PresignedInfoView,
)
from .node_management import NodeClaimView, MinerFleetView, MinerEarningsView, NodePayoutView, NodeLogProxyView

app_name = 'storage'

router = DefaultRouter()
router.register(r'buckets', BucketViewSet, basename='bucket')
router.register(r'nodes', StorageNodeViewSet, basename='node')

urlpatterns = [
    # Miner Management (Phase 29)
    path('miner/claim/', NodeClaimView.as_view(), name='node-claim'),
    path('miner/fleet/', MinerFleetView.as_view(), name='miner-fleet'),
    path('miner/earnings/', MinerEarningsView.as_view(), name='miner-earnings'),
    path('miner/payout/', NodePayoutView.as_view(), name='node-payout'),
    path('miner/logs/<str:node_id>/', NodeLogProxyView.as_view(), name='node-logs-proxy'),

    path('', include(router.urls)),
    
    # Upload/Download
    path('upload/<str:bucket_name>/', UploadView.as_view(), name='upload'),
    path('upload/multipart/init/', MultipartInitView.as_view(), name='multipart-init'),
    path('upload/multipart/<uuid:upload_id>/part/<int:part_number>/', MultipartUploadPartView.as_view(), name='multipart-part'),
    path('upload/multipart/<uuid:upload_id>/complete/', MultipartCompleteView.as_view(), name='multipart-complete'),
    
    path('stream/<uuid:object_id>/', StreamFileView.as_view(), name='stream-file'),
    
    path('download/<uuid:object_id>/', DownloadView.as_view(), name='download'),
    path('download/status/<str:task_id>/', DownloadStatusView.as_view(), name='download-status'),
    path('download/file/<str:task_id>/', DownloadFileView.as_view(), name='download-file'),
    path('download/presigned/<str:token>/', PresignedDownloadView.as_view(), name='presigned-download'),
    path('download/presigned/<str:token>/info/', PresignedInfoView.as_view(), name='presigned-info'),
    
    # Object management
    path('object/<uuid:object_id>/', ObjectDetailView.as_view(), name='object-detail'),
    path('object/<uuid:object_id>/versions/', ObjectVersionsView.as_view(), name='object-versions'),
    path('objects/', ObjectListView.as_view(), name='object-list'),
    path('object/<uuid:object_id>/presigned/', PresignedURLView.as_view(), name='object-presigned'),
    
    # Naming (IPNS style)
    path('name/', NameRecordView.as_view(), name='name-record'),
    path('name/<str:name>/', NameRecordView.as_view(), name='name-record-detail'),
    path('resolve/<str:name>/', NameResolveView.as_view(), name='name-resolve'),
    
    # System endpoints
    path('health/', HealthView.as_view(), name='health'),
    path('metrics/', MetricsView.as_view(), name='metrics'),
    path('stats/', StatsView.as_view(), name='stats'),
]
