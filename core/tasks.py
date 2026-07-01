from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from core.utils.notifications import FCMService
from notifications.models import Notification
import time

@shared_task
def send_email_notification(subject, message, recipient_list):
    """Enviar email de forma asíncrona"""
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            fail_silently=False,
        )
        return f"Email enviado a {len(recipient_list)} destinatarios"
    except Exception as e:
        return f"Error enviando email: {str(e)}"

@shared_task
def send_push_notification(user_id, title, body, data=None):
    """Enviar notificación push de forma asíncrona"""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = User.objects.get(id=user_id)
        fcm_service = FCMService()
        
        success = fcm_service.send_notification(user, title, body, data)
        return f"Notificación enviada: {success}"
    except Exception as e:
        return f"Error enviando notificación: {str(e)}"

@shared_task
def cleanup_old_notifications():
    """Limpiar notificaciones antiguas (más de 30 días)"""
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=30)
    
    deleted_count = Notification.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['delivered', 'read']
    ).delete()[0]
    
    return f"Eliminadas {deleted_count} notificaciones antiguas"

@shared_task
def update_delivery_person_availability():
    """Actualizar disponibilidad de repartidores inactivos"""
    from django.utils import timezone
    from datetime import timedelta
    from delivery.models import DeliveryPerson
    
    # Marcar como offline a repartidores sin actualización de ubicación en 30 min
    cutoff_time = timezone.now() - timedelta(minutes=30)
    
    updated = DeliveryPerson.objects.filter(
        last_location_update__lt=cutoff_time,
        availability='available'
    ).update(availability='offline')
    
    return f"Marcados como offline: {updated} repartidores"