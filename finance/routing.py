from django.urls import re_path
from .consumers import CashTransferConsumer

websocket_urlpatterns = [
    re_path(r'ws/cash_transfers/$', CashTransferConsumer.as_asgi()),
]
