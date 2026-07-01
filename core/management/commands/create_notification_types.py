# core/management/commands/create_notification_types.py
from django.core.management.base import BaseCommand
from notifications.models import NotificationType

class Command(BaseCommand):
    help = 'Crear tipos de notificaciones básicas'
    
    def handle(self, *args, **options):
        notification_types = [
            {
                'name': 'order_confirmed',
                'description': 'Pedido confirmado por el comercio',
                'template_title': 'Pedido confirmado',
                'template_body': 'Tu pedido #{order_number} ha sido confirmado y está siendo preparado.'
            },
            {
                'name': 'order_ready',
                'description': 'Pedido listo para recoger',
                'template_title': 'Pedido listo',
                'template_body': 'Tu pedido #{order_number} está listo y será recogido pronto.'
            },
            {
                'name': 'order_on_route',
                'description': 'Pedido en camino',
                'template_title': 'Pedido en camino',
                'template_body': 'Tu pedido #{order_number} está en camino. ¡Llegará pronto!'
            },
            {
                'name': 'order_delivered',
                'description': 'Pedido entregado',
                'template_title': 'Pedido entregado',
                'template_body': 'Tu pedido #{order_number} ha sido entregado. ¡Gracias por tu compra!'
            },
            {
                'name': 'new_order',
                'description': 'Nuevo pedido para comercio',
                'template_title': 'Nuevo pedido recibido',
                'template_body': 'Has recibido un nuevo pedido #{order_number}.'
            },
            {
                'name': 'trip_accepted',
                'description': 'Viaje aceptado por conductor',
                'template_title': 'Viaje aceptado',
                'template_body': 'Tu conductor está en camino al punto de recogida.'
            },
            {
                'name': 'trip_completed',
                'description': 'Viaje completado',
                'template_title': 'Viaje completado',
                'template_body': 'Has llegado a tu destino. ¡Gracias por viajar con nosotros!'
            }
        ]
        
        for nt_data in notification_types:
            notification_type, created = NotificationType.objects.get_or_create(
                name=nt_data['name'],
                defaults=nt_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Creado tipo de notificación: {notification_type.name}')
                )
            else:
                self.stdout.write(f'Tipo de notificación ya existe: {notification_type.name}')