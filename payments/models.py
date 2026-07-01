from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

User = get_user_model()

class PaymentMethod(models.Model):
    """
    Métodos de pago del sistema
    """
    TYPE_CHOICES = [
        ('cash', 'Efectivo'),
        ('card', 'Tarjeta'),
        ('digital_wallet', 'Billetera Digital'),
        ('bank_transfer', 'Transferencia Bancaria'),
    ]
    
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    provider = models.CharField(max_length=100, blank=True)  # MercadoPago, Stripe, etc.
    is_active = models.BooleanField(default=True)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    class Meta:
        db_table = 'payment_methods'
    
    def __str__(self):
        return self.name

class Payment(models.Model):
    """
    Pagos realizados en el sistema
    """
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
        ('cancelled', 'Cancelado'),
        ('refunded', 'Reembolsado'),
    ]
    
    # Referencia genérica (puede ser Order o Trip)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.CASCADE)
    
    # Identificadores
    payment_id = models.CharField(max_length=100, unique=True)
    external_payment_id = models.CharField(max_length=200, blank=True)  # ID del proveedor
    
    # Montos
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Metadatos
    metadata = models.JSONField(default=dict, blank=True)
    failure_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.payment_id:
            import uuid
            self.payment_id = f"PAY-{str(uuid.uuid4())[:12].upper()}"
        
        # Calcular comisión y monto neto
        if self.payment_method:
            self.commission = self.amount * (self.payment_method.commission_percentage / 100)
            self.net_amount = self.amount - self.commission
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Pago {self.payment_id} - ${self.amount}"

class Refund(models.Model):
    """
    Reembolsos de pagos
    """
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
    ]
    
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    refund_id = models.CharField(max_length=100, unique=True)
    external_refund_id = models.CharField(max_length=200, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'refunds'
    
    def save(self, *args, **kwargs):
        if not self.refund_id:
            import uuid
            self.refund_id = f"REF-{str(uuid.uuid4())[:12].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Reembolso {self.refund_id} - ${self.amount}"