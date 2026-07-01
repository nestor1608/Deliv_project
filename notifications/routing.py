# notifications/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/tracking/order/(?P<order_id>\w+)/$', consumers.OrderTrackingConsumer.as_asgi()),
    re_path(r'ws/tracking/trip/(?P<trip_id>\w+)/$', consumers.TripTrackingConsumer.as_asgi()),
    re_path(r'ws/notifications/(?P<user_id>\w+)/$', consumers.NotificationConsumer.as_asgi()),
]