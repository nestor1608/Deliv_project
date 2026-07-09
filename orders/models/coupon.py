from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from vendors.models import Vendor

class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Porcentaje'),
        ('fixed', 'Monto Fijo'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=8, decimal_places=2)
    
    # Conditions
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount_cap = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Monto máximo de descuento (solo para porcentaje)")
    
    # Usage limits
    max_uses = models.PositiveIntegerField(default=0, help_text="0 = ilimitado")
    max_uses_per_user = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)
    
    # Validity
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, null=True, blank=True,
        related_name='coupons', help_text="Omitir para cupones globales")
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'coupons'
    
    def __str__(self):
        return f"{self.code} ({self.get_discount_type_display()}: {self.discount_value})"
    
    def is_valid(self, user=None):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from or now > self.valid_to:
            return False
        if self.max_uses > 0 and self.used_count >= self.max_uses:
            return False
        return True
    
    def calculate_discount(self, subtotal):
        if self.discount_type == 'percentage':
            amount = subtotal * (self.discount_value / 100)
            if self.max_discount_cap:
                amount = min(amount, self.max_discount_cap)
            return amount
        else:  # fixed
            return min(self.discount_value, subtotal)
