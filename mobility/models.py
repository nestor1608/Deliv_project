from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from customers.models import Customer
import uuid

User = get_user_model()


class Driver(models.Model):
    """
    Perfil de conductor para viajes
    """

    STATUS_CHOICES = (
        ("pending", "Pendiente"),
        ("approved", "Aprobado"),
        ("suspended", "Suspendido"),
        ("rejected", "Rechazado"),
    )

    AVAILABILITY_CHOICES = (
        ("available", "Disponible"),
        ("busy", "Ocupado"),
        ("offline", "Desconectado"),
    )

    VEHICLE_CHOICES = (
        ("car", "Auto"),
        ("motorcycle", "Moto"),
        ("van", "Camioneta"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="driver_profile")
    license_number = models.CharField(max_length=50, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_CHOICES)
    vehicle_brand = models.CharField(max_length=50)
    vehicle_model = models.CharField(max_length=50)
    vehicle_year = models.PositiveIntegerField()
    vehicle_plate = models.CharField(max_length=20, unique=True)
    vehicle_color = models.CharField(max_length=30)

    # Estado y ubicación
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default="offline")
    current_latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    current_longitude = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)
    last_location_update = models.DateTimeField(blank=True, null=True)

    # KYC fields
    id_document_front = models.ImageField(upload_to="kyc/driver/", blank=True, null=True)
    id_document_back = models.ImageField(upload_to="kyc/driver/", blank=True, null=True)
    selfie = models.ImageField(upload_to="kyc/driver/", blank=True, null=True)
    background_check_status = models.CharField(
        max_length=20,
        choices=[
            ("not_submitted", "No enviado"),
            ("pending", "Pendiente"),
            ("approved", "Aprobado"),
            ("rejected", "Rechazado"),
        ],
        default="not_submitted",
    )
    kyc_submitted_at = models.DateTimeField(null=True, blank=True)
    kyc_verified_at = models.DateTimeField(null=True, blank=True)

    # Métricas
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_trips = models.PositiveIntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "drivers"

    def __str__(self):
        return f"Conductor: {self.user.get_full_name()} - {self.vehicle_brand} {self.vehicle_model}"


class Trip(models.Model):
    """
    Modelo para viajes de movilidad
    """

    STATUS_CHOICES = [
        ("requested", "Solicitado"),
        ("accepted", "Aceptado"),
        ("driver_arrived", "Conductor llegó"),
        ("in_progress", "En progreso"),
        ("completed", "Completado"),
        ("cancelled_customer", "Cancelado por cliente"),
        ("cancelled_driver", "Cancelado por conductor"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pendiente"),
        ("paid", "Pagado"),
        ("failed", "Fallido"),
        ("refunded", "Reembolsado"),
    ]

    # Identificación
    trip_number = models.CharField(max_length=20, unique=True, blank=True)

    # Relaciones
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="trips")
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name="trips")

    # Estado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending")

    # Ubicaciones
    pickup_address = models.TextField()
    pickup_latitude = models.DecimalField(max_digits=10, decimal_places=8)
    pickup_longitude = models.DecimalField(max_digits=11, decimal_places=8)

    destination_address = models.TextField()
    destination_latitude = models.DecimalField(max_digits=10, decimal_places=8)
    destination_longitude = models.DecimalField(max_digits=11, decimal_places=8)

    # Información del viaje
    estimated_distance = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)  # km
    estimated_duration = models.PositiveIntegerField(null=True, blank=True)  # minutos
    actual_distance = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    actual_duration = models.PositiveIntegerField(null=True, blank=True)

    # Precios
    base_fare = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    distance_fare = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    time_fare = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    surge_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.0)
    total_fare = models.DecimalField(max_digits=8, decimal_places=2)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Notas
    customer_notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        db_table = "trips"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.trip_number:
            self.trip_number = f"TRIP-{str(uuid.uuid4())[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Viaje {self.trip_number} - {self.customer.user.username}"


class TripRating(models.Model):
    """
    Calificaciones de viajes
    """

    RATING_TYPE_CHOICES = [
        ("customer_to_driver", "Cliente a Conductor"),
        ("driver_to_customer", "Conductor a Cliente"),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="ratings")
    rating_type = models.CharField(max_length=20, choices=RATING_TYPE_CHOICES)
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "trip_ratings"
        unique_together = ["trip", "rating_type"]

    def __str__(self):
        return f"Calificación {self.trip.trip_number} - {self.get_rating_type_display()}"
