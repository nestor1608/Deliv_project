from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from orders.models import Order
from customers.models import Customer

User = get_user_model()

class DeliveryPerson(models.Model):
    """
    Perfil de repartidor
    """
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('suspended', 'Suspendido'),
        ('rejected', 'Rechazado'),
    )
    
    AVAILABILITY_CHOICES = (
        ('available', 'Disponible'),
        ('busy', 'Ocupado'),
        ('offline', 'Desconectado'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='delivery_profile')
    license_number = models.CharField(max_length=50, unique=True)
    vehicle_type = models.CharField(max_length=50)  # Moto, Bicicleta, Auto
    vehicle_plate = models.CharField(max_length=20)
    
    # Estado y ubicación
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='offline')
    current_latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    current_longitude = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)
    last_location_update = models.DateTimeField(blank=True, null=True)
    
    # Métricas
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_deliveries = models.PositiveIntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'delivery_persons'
    
    def __str__(self):
        return f"Repartidor: {self.user.username}"


class DeliveryRating(models.Model):
    """
    Calificaciones de repartidores
    """
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    delivery_person = models.ForeignKey(DeliveryPerson, on_delete=models.CASCADE)
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'delivery_ratings'
        unique_together = ['customer', 'order']