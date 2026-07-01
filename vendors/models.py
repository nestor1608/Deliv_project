from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from customers.models import Customer

User = get_user_model()

class VendorCategory(models.Model):
    """
    Categorías de comercios (Restaurantes, Supermercados, Farmacias, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'vendor_categories'
        verbose_name_plural = 'Vendor Categories'
    
    def __str__(self):
        return self.name

class Vendor(models.Model):
    """
    Perfil de comercio/negocio
    """
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('suspended', 'Suspendido'),
        ('rejected', 'Rechazado'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    business_name = models.CharField(max_length=200)
    category = models.ForeignKey(VendorCategory, on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    business_license = models.CharField(max_length=100, unique=True)
    tax_id = models.CharField(max_length=50, unique=True)
    
    # Información de contacto
    address = models.TextField()
    latitude = models.DecimalField(max_digits=10, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)
    
    # Configuración del negocio
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    minimum_order = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    delivery_time = models.PositiveIntegerField(default=30)  # minutos
    delivery_radius = models.PositiveIntegerField(default=5)  # km
    
    # Estado y métricas
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_orders = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Horarios de atención
    is_open = models.BooleanField(default=True)
    opening_time = models.TimeField()
    closing_time = models.TimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vendors'
    
    def __str__(self):
        return self.business_name

class Product(models.Model):
    """
    Productos ofrecidos por los comercios
    """
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    category = models.CharField(max_length=100)
    
    # Inventario
    stock = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(default=True)
    
    # Métricas
    times_ordered = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'products'
    
    def __str__(self):
        return f"{self.name} - {self.vendor.business_name}"

class VendorRating(models.Model):
    """
    Calificaciones de comercios
    """
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'vendor_ratings'
        unique_together = ['customer', 'order']