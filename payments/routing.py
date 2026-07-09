# payments/routing.py
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/payments/(?P<payment_id>\d+)/$", consumers.PaymentConsumer.as_asgi()),
]
