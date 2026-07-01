from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import models
from django.utils import timezone
from .models import Trip, TripRating, Driver
from core.utils.notifications import FCMService
from core.utils.driver_assignment import DriverAssignmentService

@receiver(post_save, sender=Trip)
def trip_created(sender, instance, created, **kwargs):
    """Cuando se crea un nuevo viaje"""
    if created:
        # Asignar conductor automáticamente
        success = DriverAssignmentService.assign_trip_to_driver(instance)
        
        if not success:
            # Notificar al cliente que no hay conductores disponibles
            fcm_service = FCMService()
            fcm_service.send_notification(
                instance.customer.user,
                'No hay conductores disponibles',
                'En este momento no hay conductores disponibles en tu zona. Intenta nuevamente en unos minutos.',
                {
                    'trip_id': instance.id,
                    'type': 'no_drivers_available'
                }
            )

@receiver(pre_save, sender=Trip)
def trip_status_change(sender, instance, **kwargs):
    """Detectar cambios de estado en viajes"""
    if instance.pk:
        try:
            old_instance = Trip.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Enviar notificación según el nuevo estado
                fcm_service = FCMService()
                
                if instance.status == 'accepted':
                    fcm_service.send_notification(
                        instance.customer.user,
                        'Conductor asignado',
                        f'Tu conductor {instance.driver.user.get_full_name()} está en camino',
                        {
                            'trip_id': instance.id,
                            'type': 'trip_accepted'
                        }
                    )
                elif instance.status == 'driver_arrived':
                    fcm_service.send_notification(
                        instance.customer.user,
                        'Tu conductor ha llegado',
                        'Tu conductor está esperándote en el punto de recogida',
                        {
                            'trip_id': instance.id,
                            'type': 'driver_arrived'
                        }
                    )
                elif instance.status == 'completed':
                    fcm_service.send_notification(
                        instance.customer.user,
                        'Viaje completado',
                        '¡Has llegado a tu destino! ¿Cómo fue tu experiencia?',
                        {
                            'trip_id': instance.id,
                            'type': 'trip_completed'
                        }
                    )
        except Trip.DoesNotExist:
            pass

@receiver(post_save, sender=TripRating)
def update_driver_rating(sender, instance, created, **kwargs):
    """Actualizar rating promedio del conductor"""
    if created and instance.rating_type == 'customer_to_driver':
        driver = instance.trip.driver
        ratings = TripRating.objects.filter(
            trip__driver=driver,
            rating_type='customer_to_driver'
        )
        avg_rating = ratings.aggregate(avg=models.Avg('rating'))['avg']
        driver.rating = round(avg_rating, 2) if avg_rating else 0
        driver.save()
