from django.urls import path
from . import inventory_consumer

websocket_urlpatterns = [
    path('ws/inventory/<int:branch_id>/', inventory_consumer.InventoryConsumer.as_asgi()),
] 