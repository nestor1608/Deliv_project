"""
Shared test factories for all apps.
Uses factory_boy to create test data efficiently.
"""

from decimal import Decimal
from datetime import time

import factory
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase as BaseAPITestCase

from customers.models import Customer, CustomerAddress
from vendors.models import VendorCategory, Vendor, Product
from orders.models import Order, OrderItem
from delivery.models import DeliveryPerson
from mobility.models import Driver
from notifications.models import NotificationType, Notification, UserDevice
from payments.models import PaymentMethod

User = get_user_model()

# Patch the security middleware to disable rate limiting in tests
import users.middleware.security as security_middleware


def _no_rate_limit(self, request):
    return None


security_middleware.SecurityMiddleware.check_rate_limit = _no_rate_limit

import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning, module="django.db.models.fields")

from unittest.mock import MagicMock

# Patch DRF throttling globally for tests
import rest_framework.throttling

rest_framework.throttling.SimpleRateThrottle.allow_request = lambda self, request, view: True

# Patch channels layer to avoid Redis connections in tests
import channels.layers

channels.layers.get_channel_layer = lambda: MagicMock()


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ],
        "DEFAULT_PERMISSION_CLASSES": [
            "rest_framework.permissions.IsAuthenticated",
        ],
        "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
        "PAGE_SIZE": 20,
        "DEFAULT_RENDERER_CLASSES": [
            "rest_framework.renderers.JSONRenderer",
        ],
        "DEFAULT_FILTER_BACKENDS": [
            "django_filters.rest_framework.DjangoFilterBackend",
            "rest_framework.filters.SearchFilter",
            "rest_framework.filters.OrderingFilter",
        ],
        "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {},
    },
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    },
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_BROKER_URL=None,
    CELERY_RESULT_BACKEND=None,
)
class APITestCase(BaseAPITestCase):
    """Base test case that disables DRF throttling and middleware rate limiting."""

    pass


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User instances."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"testuser_{n:04d}")
    email = factory.Sequence(lambda n: f"user_{n:04d}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "TestPass123!")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    phone_number = factory.Sequence(lambda n: f"+5493644123{n:04d}")
    role = "customer"
    status = "active"
    email_verified = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "TestPass123!")
        instance = super()._create(model_class, *args, **kwargs)
        # Ensure password is properly hashed
        instance.set_password(password)
        instance.save(update_fields=["password"])
        return instance


class CustomerFactory(factory.django.DjangoModelFactory):
    """Factory for creating Customer profiles."""

    class Meta:
        model = Customer

    user = factory.SubFactory(UserFactory, role="customer")
    date_of_birth = factory.Faker("date_of_birth")
    loyalty_points = 0
    preferred_payment_method = "cash"
    is_premium = False
    phone_verified = False


class CustomerAddressFactory(factory.django.DjangoModelFactory):
    """Factory for creating CustomerAddress instances."""

    class Meta:
        model = CustomerAddress

    customer = factory.SubFactory(CustomerFactory)
    label = factory.Sequence(lambda n: f"Address {n}")
    street_address = factory.Faker("street_address")
    city = factory.Faker("city")
    state = factory.Faker("state")
    postal_code = factory.Faker("postcode")
    country = "Argentina"
    is_default = False


class VendorCategoryFactory(factory.django.DjangoModelFactory):
    """Factory for creating VendorCategory instances."""

    class Meta:
        model = VendorCategory

    name = factory.Sequence(lambda n: f"Category {n}")
    description = factory.Faker("text", max_nb_chars=200)
    is_active = True


class VendorFactory(factory.django.DjangoModelFactory):
    """Factory for creating Vendor (business) profiles."""

    class Meta:
        model = Vendor

    user = factory.SubFactory(UserFactory, role="vendor")
    business_name = factory.Sequence(lambda n: f"Business {n}")
    category = factory.SubFactory(VendorCategoryFactory)
    description = factory.Faker("text", max_nb_chars=300)
    business_license = factory.Sequence(lambda n: f"LIC-{n:06d}")
    tax_id = factory.Sequence(lambda n: f"TAX-{n:06d}")
    address = factory.Faker("address")
    latitude = Decimal("-31.6625")
    longitude = Decimal("-60.7676")
    delivery_fee = Decimal("150.00")
    minimum_order = Decimal("500.00")
    delivery_time = 30
    delivery_radius = 5
    status = "approved"
    rating = Decimal("4.50")
    total_orders = 0
    is_open = True
    opening_time = time(8, 0)
    closing_time = time(22, 0)


class ProductFactory(factory.django.DjangoModelFactory):
    """Factory for creating Product instances."""

    class Meta:
        model = Product

    vendor = factory.SubFactory(VendorFactory)
    name = factory.Sequence(lambda n: f"Product {n}")
    description = factory.Faker("text", max_nb_chars=200)
    price = Decimal("100.00")
    category = "General"
    stock = 100
    is_available = True
    times_ordered = 0


class DeliveryPersonFactory(factory.django.DjangoModelFactory):
    """Factory for creating DeliveryPerson profiles."""

    class Meta:
        model = DeliveryPerson

    user = factory.SubFactory(UserFactory, role="delivery")
    license_number = factory.Sequence(lambda n: f"DL-{n:06d}")
    vehicle_type = "Moto"
    vehicle_plate = factory.Sequence(lambda n: f"ABC{n:03d}")
    status = "approved"
    availability = "available"
    rating = Decimal("4.50")
    total_deliveries = 0
    total_earnings = Decimal("0.00")


class DriverFactory(factory.django.DjangoModelFactory):
    """Factory for creating Driver profiles."""

    class Meta:
        model = Driver

    user = factory.SubFactory(UserFactory, role="delivery")
    license_number = factory.Sequence(lambda n: f"DRV-{n:06d}")
    vehicle_type = "car"
    vehicle_brand = "Toyota"
    vehicle_model = "Corolla"
    vehicle_year = 2020
    vehicle_plate = factory.Sequence(lambda n: f"DRV{n:03d}")
    vehicle_color = "Blanco"
    status = "approved"
    availability = "available"
    rating = Decimal("4.50")
    total_trips = 0
    total_earnings = Decimal("0.00")


def create_order_with_items(customer=None, vendor=None, product=None, quantity=2):
    """Helper to create an order with items for testing."""
    if customer is None:
        customer = CustomerFactory()
    if vendor is None:
        vendor = VendorFactory()
    if product is None:
        product = ProductFactory(vendor=vendor)

    unit_price = product.price
    total_price = unit_price * quantity

    order = Order.objects.create(
        customer=customer,
        vendor=vendor,
        delivery_address="Test Address 123",
        delivery_latitude=Decimal("-31.6625"),
        delivery_longitude=Decimal("-60.7676"),
        subtotal=total_price,
        delivery_fee=Decimal("150.00"),
        tax_amount=total_price * Decimal("0.21"),
        total_amount=total_price + Decimal("150.00") + (total_price * Decimal("0.21")),
        status="pending",
        payment_status="pending",
    )

    OrderItem.objects.create(
        order=order,
        product=product,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
    )

    return order


class NotificationTypeFactory(factory.django.DjangoModelFactory):
    """Factory for creating NotificationType instances."""

    class Meta:
        model = NotificationType

    name = factory.Sequence(lambda n: f"notification_type_{n}")
    description = factory.Faker("text", max_nb_chars=200)
    template_title = factory.Sequence(lambda n: f"Title {n}")
    template_body = factory.Faker("text", max_nb_chars=200)
    is_active = True


class NotificationFactory(factory.django.DjangoModelFactory):
    """Factory for creating Notification instances."""

    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    notification_type = factory.SubFactory(NotificationTypeFactory)
    title = factory.Sequence(lambda n: f"Notification {n}")
    body = factory.Faker("text", max_nb_chars=200)
    status = "sent"


class UserDeviceFactory(factory.django.DjangoModelFactory):
    """Factory for creating UserDevice instances."""

    class Meta:
        model = UserDevice

    user = factory.SubFactory(UserFactory)
    fcm_token = factory.Sequence(lambda n: f"fcm_token_{n:020d}")
    platform = "android"
    device_id = factory.Sequence(lambda n: f"device_{n:010d}")
    app_version = "1.0.0"
    is_active = True


class PaymentMethodFactory(factory.django.DjangoModelFactory):
    """Factory for creating PaymentMethod instances."""

    class Meta:
        model = PaymentMethod

    name = factory.Sequence(lambda n: f"Payment Method {n}")
    type = "cash"
    provider = "cash"
    is_active = True
    commission_percentage = Decimal("0.00")


def create_vendor_rating(customer=None, vendor=None, order=None, rating=5):
    """Helper to create a vendor rating for testing."""
    from vendors.models import VendorRating

    if customer is None:
        customer = CustomerFactory()
    if vendor is None:
        vendor = VendorFactory()
    if order is None:
        order = create_order_with_items(
            customer=customer,
            vendor=vendor,
        )
        order.status = "delivered"
        order.save()

    return VendorRating.objects.create(
        customer=customer, vendor=vendor, order=order, rating=rating, comment="Great service!"
    )


def create_delivery_rating(customer=None, delivery_person=None, order=None, rating=5):
    """Helper to create a delivery rating for testing."""
    from delivery.models import DeliveryRating

    if customer is None:
        customer = CustomerFactory()
    if delivery_person is None:
        delivery_person = DeliveryPersonFactory()
    if order is None:
        order = create_order_with_items(customer=customer)
        order.status = "delivered"
        order.delivery_person = delivery_person
        order.save()

    return DeliveryRating.objects.create(
        customer=customer, delivery_person=delivery_person, order=order, rating=rating, comment="Fast delivery!"
    )
