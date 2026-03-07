from django.urls import path
from . import views

urlpatterns = [
    # Phase 10 — Core conversations & messaging
    path('conversations/', views.ConversationListView.as_view(), name='conversations-list'),
    path('conversations/<uuid:conversation_id>/', views.ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<uuid:conversation_id>/send/', views.SendMessageView.as_view(), name='message-send'),
    path('conversations/<uuid:conversation_id>/messages/<uuid:message_id>/decrypt/', views.MessageDecryptView.as_view(), name='message-decrypt'),
    path('inbox/', views.InboxView.as_view(), name='messaging-inbox'),
    path('inbox/dht/', views.DHTInboxView.as_view(), name='messaging-inbox-dht'),

    # Phase 12 — File attachments
    path('conversations/<uuid:conversation_id>/attach/', views.MessageAttachView.as_view(), name='message-attach'),

    # Phase 13 — Group management
    path('conversations/<uuid:conversation_id>/members/', views.GroupInviteView.as_view(), name='group-members'),

    # Phase 14 — Search & expiry
    path('search/', views.MessageSearchView.as_view(), name='message-search'),
    path('admin/expire/', views.MessageExpireView.as_view(), name='message-expire'),
]
