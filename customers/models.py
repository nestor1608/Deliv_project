from django.db import models
from django.conf import settings


class Customer(models.Model):
    """
    Perfil extendido para usuarios con rol de cliente
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_profile")
    date_of_birth = models.DateField(null=True, blank=True)
    loyalty_points = models.PositiveIntegerField(default=0)
    preferred_payment_method = models.CharField(
        max_length=50,
        default="cash",
        choices=[
            ("cash", "Efectivo"),
            ("card", "Tarjeta"),
            ("digital_wallet", "Billetera Digital"),
        ],
    )
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers"

    def __str__(self):
        return f"Cliente: {self.user.get_full_name()}"


class CustomerAddress(models.Model):
    """
    Direcciones guardadas por el cliente
    """

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=50, help_text="Ej: Casa, Trabajo, etc.")
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="Argentina")
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customer_addresses"
        unique_together = ["customer", "label"]

    def __str__(self):
        return f"{self.label} - {self.customer.user.username}"
