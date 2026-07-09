# deliv_ST/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'deliv_ST.settings')

# Import all routing modules
import notifications.routing
import orders.routing
import mobility.routing
import payments.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            notifications.routing.websocket_urlpatterns
            + orders.routing.websocket_urlpatterns
            + mobility.routing.websocket_urlpatterns
            + payments.routing.websocket_urlpatterns
        )
    ),
})
