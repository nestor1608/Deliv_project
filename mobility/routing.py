# mobility/routing.py
from django.urls import re_path
from notifications.consumers import TripTrackingConsumer

websocket_urlpatterns = [
    re_path(r'ws/trips/(?P<trip_id>\w+)/$', TripTrackingConsumer.as_asgi()),
]
