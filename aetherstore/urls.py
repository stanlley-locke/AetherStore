from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/storage/', include('apps.storage.urls')),
    path('api/v1/billing/', include('apps.billing.urls')),
    path('api/v1/messaging/', include('apps.messaging.urls')),
    path('api/v1/p2p/', include('apps.p2p.urls')),
    path('health/', TemplateView.as_view(template_name='health.html'), name='health'),
    path('docs/', TemplateView.as_view(template_name='docs.html'), name='docs'),
]