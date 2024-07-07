import os
from channels.auth import AuthMiddlewareStack 
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import inventory.routing
import finance.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "techcity.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),  
    "websocket": AuthMiddlewareStack(
        URLRouter(
            inventory.routing.websocket_urlpatterns, 
            finance.routing.websocket_urlpatterns, 
        )
    ),
})
