from django.contrib.auth import get_user_model
from tests.factories import APITestCase
from rest_framework import status
from decimal import Decimal
from orders.models import Order, OrderItem
from vendors.models import Vendor, VendorCategory, Product
from customers.models import Customer

User = get_user_model()


class OrderTestCase(APITestCase):
    def setUp(self):
        # Crear usuario cliente
        self.customer_user = User.objects.create_user(
            username="testcustomer",
            email="customer@test.com",
            password="testpass123",
            role="customer",
            phone_number="+5493644123456",
        )

        self.customer = Customer.objects.create(user=self.customer_user)

        # Crear usuario comercio
        self.vendor_user = User.objects.create_user(
            username="testvendor",
            email="vendor@test.com",
            password="testpass123",
            role="vendor",
            phone_number="+5493644123457",
        )

        # Crear categoría y comercio
        self.category = VendorCategory.objects.create(name="Test Category")
        self.vendor = Vendor.objects.create(
            user=self.vendor_user,
            business_name="Test Business",
            category=self.category,
            address="Test Address",
            latitude=Decimal("-31.6625"),
            longitude=Decimal("-60.7676"),
            business_license="TEST001",
            tax_id="TAX001",
            opening_time="08:00",
            closing_time="22:00",
            status="approved",
        )

        # Crear producto
        self.product = Product.objects.create(
            vendor=self.vendor,
            name="Test Product",
            price=Decimal("100.00"),
            category="Test",
            stock=10,
            is_available=True,
        )

    def test_create_order(self):
        """Test crear un nuevo pedido"""
        self.client.force_authenticate(user=self.customer_user)

        data = {
            "vendor": self.vendor.id,
            "delivery_address": "Test Delivery Address",
            "delivery_latitude": -31.6625,
            "delivery_longitude": -60.7676,
            "customer_notes": "Test notes",
            "items": [{"product_id": self.product.id, "quantity": 2, "special_instructions": "Extra sauce"}],
        }

        response = self.client.post("/api/orders/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verificar que se creó el pedido
        order = Order.objects.get(id=response.data["id"])
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.vendor, self.vendor)
        self.assertEqual(order.items.count(), 1)

    def test_order_total_calculation(self):
        """Test cálculo correcto del total del pedido"""
        order = Order.objects.create(
            customer=self.customer,
            vendor=self.vendor,
            delivery_address="Test Address",
            subtotal=Decimal("200.00"),
            delivery_fee=Decimal("150.00"),
            tax_amount=Decimal("42.00"),
            total_amount=Decimal("392.00"),
        )

        OrderItem.objects.create(
            order=order, product=self.product, quantity=2, unit_price=self.product.price, total_price=Decimal("200.00")
        )

        self.assertEqual(order.total_amount, Decimal("392.00"))
