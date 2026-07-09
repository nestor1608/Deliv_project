from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Order, OrderStatusHistory
from notifications.models import Notification, NotificationType
from delivery.models import DeliveryPerson


@receiver(pre_save, sender=Order)
def order_status_change(sender, instance, **kwargs):
    """Detectar cambios de estado en pedidos"""
    if instance.pk:
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Crear entrada en historial
                OrderStatusHistory.objects.create(
                    order=instance,
                    previous_status=old_instance.status,
                    new_status=instance.status,
                    timestamp=timezone.now(),
                )

                # Enviar notificación en tiempo real
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"order_{instance.id}",
                    {
                        "type": "status_update",
                        "status": instance.status,
                        "message": f"Tu pedido está {instance.get_status_display().lower()}",
                        "timestamp": timezone.now().isoformat(),
                    },
                )

                # Crear notificación push
                create_order_notification(instance, instance.status)

        except Order.DoesNotExist:
            pass


@receiver(post_save, sender=Order)
def order_created(sender, instance, created, **kwargs):
    """Cuando se crea un nuevo pedido"""
    if created:
        # Asignar repartidor disponible más cercano (lógica básica)
        assign_delivery_person(instance)

        # Notificar al comercio
        create_vendor_notification(instance)


def assign_delivery_person(order):
    """Lógica simple para asignar repartidor"""
    available_delivery = DeliveryPerson.objects.filter(status="approved", availability="available").first()

    if available_delivery:
        order.delivery_person = available_delivery
        available_delivery.availability = "busy"
        available_delivery.save()
        order.save()


def create_order_notification(order, status):
    """Crear notificación para cambio de estado"""
    try:
        notification_type = NotificationType.objects.get(name=f"order_{status}")

        Notification.objects.create(
            user=order.customer.user,
            notification_type=notification_type,
            title=notification_type.template_title.format(order_number=order.order_number),
            body=notification_type.template_body.format(
                order_number=order.order_number, status=order.get_status_display()
            ),
            data={"order_id": order.id, "order_number": order.order_number, "status": status},
        )
    except NotificationType.DoesNotExist:
        pass


def create_vendor_notification(order):
    """Notificar al comercio sobre nuevo pedido"""
    try:
        notification_type = NotificationType.objects.get(name="new_order")

        Notification.objects.create(
            user=order.vendor.user,
            notification_type=notification_type,
            title="Nuevo pedido recibido",
            body=f"Pedido #{order.order_number} por ${order.total_amount}",
            data={
                "order_id": order.id,
                "order_number": order.order_number,
                "customer_name": order.customer.user.get_full_name(),
            },
        )
    except NotificationType.DoesNotExist:
        pass
