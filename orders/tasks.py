import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task
def process_scheduled_orders():
    """
    Every minute, transition 'scheduled' orders whose scheduled_time has passed
    to 'confirmed' status.
    """
    from .models import Order

    now = timezone.now()
    due_orders = Order.objects.filter(
        status='scheduled',
        scheduled_time__lte=now,
        scheduled_time__gte=now - timedelta(days=1)
    )

    count = 0
    for order in due_orders:
        order.status = 'confirmed'
        order.confirmed_at = timezone.now()
        order.save(update_fields=['status', 'confirmed_at', 'updated_at'])
        count += 1

        from notifications.services import notify_user
        notify_user(
            order.customer.user,
            'Pedido en proceso',
            f'Tu pedido #{order.order_number} ya está en preparación.',
            {'order_id': order.id, 'type': 'order_confirmed'}
        )

    if count:
        logger.info(f'Processed {count} scheduled order(s)')

    return {'processed': count}
