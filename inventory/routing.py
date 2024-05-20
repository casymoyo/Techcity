from django.urls import path
from . import consumer

websocket_urlpatterns = [
    path('ws/inventory/<int:branch_id>/', consumer.InventoryConsumer.as_asgi()),
] 