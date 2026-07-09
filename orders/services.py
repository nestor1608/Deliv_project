import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)

def validate_and_apply_coupon(code, subtotal, vendor=None, user=None):
    """
    Validate a coupon code and return discount info.
    Returns dict with success, discount_amount, and message.
    """
    from .models.coupon import Coupon
    
    try:
        coupon = Coupon.objects.get(code__iexact=code.strip())
    except Coupon.DoesNotExist:
        return {'success': False, 'message': 'Cupón inválido', 'discount_amount': Decimal('0')}
    
    if not coupon.is_valid(user):
        return {'success': False, 'message': 'Cupón expirado o no disponible', 'discount_amount': Decimal('0')}
    
    if vendor and coupon.vendor and coupon.vendor != vendor:
        return {'success': False, 'message': 'Cupón no válido para este comercio', 'discount_amount': Decimal('0')}
    
    if subtotal < coupon.min_order_amount:
        return {
            'success': False,
            'message': f'Pedido mínimo: ${coupon.min_order_amount}',
            'discount_amount': Decimal('0')
        }
    
    discount_amount = coupon.calculate_discount(subtotal)
    
    return {
        'success': True,
        'message': f'Cupón aplicado: {coupon.code}',
        'discount_amount': discount_amount,
        'coupon': coupon,
    }

def apply_coupon_to_order(order, coupon_code):
    """
    Apply a coupon to an existing order and recalculate totals.
    """
    from .models.coupon import Coupon
    from decimal import Decimal
    
    try:
        coupon = Coupon.objects.get(code__iexact=coupon_code.strip())
    except Coupon.DoesNotExist:
        return {'success': False, 'message': 'Cupón inválido'}
    
    result = validate_and_apply_coupon(coupon_code, order.subtotal, order.vendor, order.customer.user)
    
    if not result['success']:
        return result
    
    # Apply discount
    order.discount_amount = result['discount_amount']
    order.coupon = coupon
    order.total_amount = order.subtotal + order.delivery_fee + order.tax_amount - order.discount_amount
    order.save(update_fields=['discount_amount', 'coupon', 'total_amount', 'updated_at'])
    
    # Increment usage counter
    Coupon.objects.filter(id=coupon.id).update(used_count=models.F('used_count') + 1)
    
    return {'success': True, 'message': f'Descuento de ${result["discount_amount"]} aplicado', 'discount_amount': result['discount_amount']}
