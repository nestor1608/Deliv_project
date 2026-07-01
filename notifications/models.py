from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class NotificationType(models.Model):
    """
    Tipos de notificaciones del sistema
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    template_title = models.CharField(max_length=200)
    template_body = models.TextField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'notification_types'
    
    def __str__(self):
        return self.name

class Notification(models.Model):
    """
    Notificaciones enviadas a usuarios
    """
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('sent', 'Enviada'),
        ('delivered', 'Entregada'),
        ('read', 'Leída'),
        ('failed', 'Fallida'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.ForeignKey(NotificationType, on_delete=models.CASCADE)
    
    title = models.CharField(max_length=200)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # Datos adicionales
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Para push notifications
    fcm_token = models.TextField(blank=True)
    message_id = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"

class UserDevice(models.Model):
    """
    Dispositivos de usuarios para push notifications
    """
    PLATFORM_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    fcm_token = models.TextField(unique=True)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    device_id = models.CharField(max_length=200, blank=True)
    app_version = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_devices'
        unique_together = ['user', 'device_id']
    
    def __str__(self):
        return f"{self.user.username} - {self.platform}"