# orders/routing.py
from django.urls import re_path
from notifications.consumers import OrderTrackingConsumer

websocket_urlpatterns = [
    re_path(r"ws/orders/(?P<order_id>\w+)/$", OrderTrackingConsumer.as_asgi()),
]
