from decimal import Decimal
from django.db import models
from django.conf import settings
from vendors.models import Vendor, Product 


class Order(models.Model):
    """
    Modelo principal para pedidos
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('scheduled', 'Programado'),
        ('confirmed', 'Confirmado'),
        ('preparing', 'Preparando'),
        ('ready', 'Listo'),
        ('on_route', 'En camino'),
        ('delivered', 'Entregado'),
        ('cancelled', 'Cancelado'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('failed', 'Fallido'),
        ('refunded', 'Reembolsado'),
    ]
    
    # Relaciones principales
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='orders'
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    # delivery_person = models.ForeignKey(
    #     settings.AUTH_USER_MODEL,
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='delivery_orders',
    #     limit_choices_to={'role': 'delivery'}
    # )
    delivery_person = models.ForeignKey(
    'delivery.DeliveryPerson',  # Referencia al modelo DeliveryPerson
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='assigned_orders'
)
    
    # Información del pedido
    order_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    
    # Dirección de entrega
    delivery_address = models.TextField()
    delivery_latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=8, 
        null=True, 
        blank=True
    )
    delivery_longitude = models.DecimalField(
        max_digits=11, 
        decimal_places=8, 
        null=True, 
        blank=True
    )
    
    # Precios y tiempos
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    estimated_delivery_time = models.DateTimeField(null=True, blank=True)
    
    # Notas y observaciones
    customer_notes = models.TextField(blank=True)
    scheduled_time = models.DateTimeField(null=True, blank=True, help_text="Fecha/hora programada para el pedido")
    vendor_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['vendor']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['scheduled_time']),
        ]
    
    def __str__(self):
        return f"Pedido {self.order_number} - {self.customer.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generar número de pedido único
            import uuid
            self.order_number = f"ORD-{str(uuid.uuid4())[:8].upper()}"
        super().save(*args, **kwargs)

class OrderItem(models.Model):
    """
    Productos incluidos en cada pedido
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    special_instructions = models.TextField(blank=True)
    
    class Meta:
        db_table = 'order_items'
        unique_together = ['order', 'product']
    
    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

class OrderStatusHistory(models.Model):
    """
    Historial de cambios de estado del pedido
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_history'
    )
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_status_history'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.order.order_number}: {self.previous_status} → {self.new_status}"