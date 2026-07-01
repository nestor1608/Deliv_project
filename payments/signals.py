from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Payment
from core.utils.notifications import FCMService

@receiver(post_save, sender=Payment)
def payment_status_change(sender, instance, created, **kwargs):
    """Notificar cambios en el estado de pagos"""
    if not created:  # Solo cuando se actualiza, no cuando se crea
        fcm_service = FCMService()
        
        if instance.status == 'completed':
            fcm_service.send_notification(
                instance.user,
                'Pago exitoso',
                f'Tu pago de ${instance.amount} ha sido procesado correctamente',
                {
                    'payment_id': instance.payment_id,
                    'type': 'payment_completed'
                }
            )
        elif instance.status == 'failed':
            fcm_service.send_notification(
                instance.user,
                'Error en el pago',
                'Hubo un problema procesando tu pago. Intenta nuevamente.',
                {
                    'payment_id': instance.payment_id,
                    'type': 'payment_failed'
                }
            )