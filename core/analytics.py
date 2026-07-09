import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Avg
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutos

def get_dashboard_data(days=30):
    """
    Get aggregated analytics for the admin dashboard.
    Cached for 5 minutes.
    """
    cache_key = f'admin_dashboard_{days}'
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    start_date = timezone.now() - timedelta(days=days)
    
    # Avoid circular imports - import here
    from orders.models import Order
    from payments.models import Payment
    from vendors.models import Vendor
    from delivery.models import DeliveryPerson
    from mobility.models import Driver
    
    data = {}
    
    # Revenue
    payments = Payment.objects.filter(created_at__gte=start_date, status='completed')
    data['total_revenue'] = float(payments.aggregate(total=Sum('amount'))['total'] or 0)
    data['total_commission'] = float(payments.aggregate(total=Sum('commission'))['total'] or 0)
    
    # Orders
    orders = Order.objects.filter(created_at__gte=start_date)
    data['total_orders'] = orders.count()
    data['orders_by_status'] = list(orders.values('status').annotate(count=Count('id')).order_by('status'))
    
    # Daily revenue (last 7 days)
    daily = []
    for i in range(7):
        date = timezone.now().date() - timedelta(days=i)
        day_payments = payments.filter(created_at__date=date)
        day_orders = orders.filter(created_at__date=date)
        daily.append({
            'date': date.isoformat(),
            'revenue': float(day_payments.aggregate(total=Sum('amount'))['total'] or 0),
            'orders': day_orders.count(),
        })
    data['daily_stats'] = daily
    
    # Vendors
    data['active_vendors'] = Vendor.objects.filter(status='approved').count()
    data['top_vendors'] = list(
        orders.values('vendor__business_name').annotate(
            total=Sum('total_amount'), count=Count('id')
        ).order_by('-total')[:10]
    )
    
    # Delivery
    data['active_delivery'] = DeliveryPerson.objects.filter(availability='available').count()
    data['total_delivery'] = DeliveryPerson.objects.count()
    
    # Mobility
    data['active_drivers'] = Driver.objects.filter(availability='available').count()
    data['total_drivers'] = Driver.objects.count()
    
    # Platform totals
    data['total_platform_revenue'] = float(
        Payment.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
    )
    data['total_platform_orders'] = Order.objects.count()
    
    cache.set(cache_key, data, CACHE_TTL)
    return data
