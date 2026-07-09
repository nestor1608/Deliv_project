# core/utils/notifications.py
import requests
import json
from django.conf import settings
from notifications.models import Notification, UserDevice


class FCMService:
    """Servicio para Firebase Cloud Messaging"""

    def __init__(self):
        firebase_config = getattr(settings, "FIREBASE_CONFIG", {})
        self.server_key = firebase_config.get("FCM_SERVER_KEY", "")
        self.url = "https://fcm.googleapis.com/fcm/send"

    def send_notification(self, user, title, body, data=None):
        if not self.server_key:
            return False
        """Enviar notificación push a un usuario"""
        devices = UserDevice.objects.filter(user=user, is_active=True)

        if not devices.exists():
            return False

        headers = {"Authorization": f"key={self.server_key}", "Content-Type": "application/json"}

        success_count = 0

        for device in devices:
            payload = {
                "to": device.fcm_token,
                "notification": {"title": title, "body": body, "sound": "default"},
                "data": data or {},
            }

            response = requests.post(self.url, headers=headers, data=json.dumps(payload))

            if response.status_code == 200:
                success_count += 1

                # Crear registro de notificación
                Notification.objects.create(
                    user=user, title=title, body=body, data=data or {}, status="sent", fcm_token=device.fcm_token
                )

        return success_count > 0

    def send_bulk_notification(self, users, title, body, data=None):
        """Enviar notificación a múltiples usuarios"""
        success_count = 0

        for user in users:
            if self.send_notification(user, title, body, data):
                success_count += 1

        return success_count
