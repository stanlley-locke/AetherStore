from django.urls import path
from .views import NodeHealthView, NodeActivateView
from .admin_controls import (
    NetworkParameterView,
    TreasuryAnalyticsView,
    UserQuotaManagementView,
    AdminUserManagementView,
    AdminStatusView,
)
from .log_views import SystemLogView

urlpatterns = [
    path('nodes/health/', NodeHealthView.as_view(), name='node-health-check'),
    path('nodes/activate/', NodeActivateView.as_view(), name='node-activate'),
    
    # Admin Controls
    path('admin/status/', AdminStatusView.as_view(), name='admin-status'),
    path('admin/parameters/', NetworkParameterView.as_view(), name='admin-parameters'),
    path('admin/treasury/', TreasuryAnalyticsView.as_view(), name='admin-treasury'),
    path('admin/quota/<str:did>/', UserQuotaManagementView.as_view(), name='admin-user-quota'),
    path('admin/users/', AdminUserManagementView.as_view(), name='admin-users'),
    path('admin/logs/system/', SystemLogView.as_view(), name='admin-system-logs'),
]
