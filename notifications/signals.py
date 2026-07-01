from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification
from core.tasks import send_push_notification

@receiver(post_save, sender=Notification)
def send_notification_async(sender, instance, created, **kwargs):
    """Enviar notificación push cuando se crea una nueva notificación"""
    if created and instance.status == 'pending':
        # Enviar notificación de forma asíncrona usando Celery
        send_push_notification.delay(
            instance.user.id,
            instance.title,
            instance.body,
            instance.data
        )