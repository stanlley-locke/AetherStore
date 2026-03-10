from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('wallet/', views.WalletBalanceView.as_view(), name='wallet_balance'),
    path('wallet/generate/', views.WalletCreateView.as_view(), name='wallet_generate'),
    path('wallet/transfer/', views.WalletTransferView.as_view(), name='wallet_transfer'),
    path('wallet/recover/', views.WalletRecoveryView.as_view(), name='wallet_recover'),
    path('wallet/resolve/<str:address>/', views.WalletResolveView.as_view(), name='wallet_resolve'),
    path('deposit/', views.DepositFundsView.as_view(), name='wallet_deposit'),
    path('node/<str:node_id>/earnings/', views.NodeEarningsView.as_view(), name='node_earnings'),
]
