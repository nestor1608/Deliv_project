from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator

class User(AbstractUser):
    """
    Modelo de usuario personalizado que extiende AbstractUser
    Soporta múltiples roles: Cliente, Comercio, Repartidor, Admin
    """
    
    ROLE_CHOICES = [
        ('customer', 'Cliente'),
        ('vendor', 'Comercio'),
        ('delivery', 'Repartidor'),
        ('admin', 'Administrador'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('suspended', 'Suspendido'),
    ]
    
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='customer',
        help_text="Rol del usuario en el sistema"
    )
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$', 
        message="Formato de teléfono inválido. Ej: +5493644123456"
    )
    phone_number = models.CharField(
        validators=[phone_regex], 
        max_length=17, 
        unique=True,
        help_text="Número de teléfono con código de país"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='active'
    )
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    profile_picture = models.ImageField(
        upload_to='profile_pics/', 
        null=True, 
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def is_customer(self):
        return self.role == 'customer'
    
    def is_vendor(self):
        return self.role == 'vendor'
    
    def is_delivery_person(self):
        return self.role == 'delivery'