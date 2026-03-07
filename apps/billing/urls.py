from django.urls import path
from . import views

urlpatterns = [
    path('wallet/', views.WalletBalanceView.as_view(), name='wallet_balance'),
    path('deposit/', views.DepositFundsView.as_view(), name='wallet_deposit'),
    
    path('node/<str:node_id>/earnings/', views.NodeEarningsView.as_view(), name='node_earnings'),
]
