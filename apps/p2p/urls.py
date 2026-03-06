from django.urls import path
from .views import NodeHealthView, NodeActivateView

urlpatterns = [
    path('nodes/health/', NodeHealthView.as_view(), name='node-health-check'),
    path('nodes/activate/', NodeActivateView.as_view(), name='node-activate'),
]
