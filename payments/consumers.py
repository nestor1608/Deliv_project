# payments/consumers.py
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model

from payments.models import Payment

User = get_user_model()


class PaymentConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time payment updates.
    Auth: only the payment owner or admin can connect.
    URL pattern: ws/payments/<payment_id>/
    """

    async def connect(self):
        self.payment_id = self.scope["url_route"]["kwargs"]["payment_id"]
        self.room_group_name = f"payment_{self.payment_id}"

        # Authenticate and authorize
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Verify payment exists and user has access
        has_access = await self._check_payment_access(user, self.payment_id)
        if not has_access:
            await self.close(code=4003)
            return

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        # Payments consumer is primarily for receiving updates,
        # not for sending data from client
        pass

    async def payment_update(self, event):
        """
        Send payment status update to WebSocket clients.
        Triggered by channel_layer.group_send from payment signals.
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "payment_update",
                    "payment_id": event["payment_id"],
                    "status": event["status"],
                    "status_display": event.get("status_display", ""),
                    "amount": event.get("amount"),
                    "updated_at": event.get("updated_at"),
                }
            )
        )

    @database_sync_to_async
    def _check_payment_access(self, user, payment_id):
        """Check if user has access to this payment's websocket."""
        try:
            payment = Payment.objects.get(id=payment_id)
            # Admin can see all payments
            if user.role == "admin":
                return True
            # Owner can see their own payment
            if payment.user == user:
                return True
            return False
        except Payment.DoesNotExist:
            return False
