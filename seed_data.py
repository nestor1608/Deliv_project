import os
import django
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "deliv_ST.settings")
django.setup()

from users.models import User
from customers.models import Customer
from vendors.models import Vendor, VendorCategory, Product
from delivery.models import DeliveryPerson
from orders.models import Order, OrderItem


def create_users():
    print("Creando usuarios...")
    suffix = str(uuid.uuid4())[:4]

    # Admin
    if not User.objects.filter(email="admin@deliv.com").exists():
        User.objects.create_superuser(
            f"admin_{suffix}", "admin@deliv.com", "password123", role="admin", phone_number=f"+{suffix}999999"
        )

    # Customer
    customer_user, _ = User.objects.get_or_create(
        email=f"customer_{suffix}@deliv.com",
        defaults={
            "username": f"customer_{suffix}",
            "first_name": "Carlos",
            "last_name": "Cliente",
            "role": "customer",
            "phone_number": f"+{suffix}111111",
        },
    )
    if _:
        customer_user.set_password("password123")
        customer_user.save()
        Customer.objects.create(user=customer_user)

    # Vendor
    vendor_user, _ = User.objects.get_or_create(
        email=f"vendor_{suffix}@deliv.com",
        defaults={
            "username": f"vendor_{suffix}",
            "first_name": "Victor",
            "last_name": "Vendedor",
            "role": "vendor",
            "phone_number": f"+{suffix}222222",
        },
    )
    if _:
        vendor_user.set_password("password123")
        vendor_user.save()

    # Delivery
    delivery_user, _ = User.objects.get_or_create(
        email=f"delivery_{suffix}@deliv.com",
        defaults={
            "username": f"delivery_{suffix}",
            "first_name": "Diego",
            "last_name": "Delivery",
            "role": "delivery",
            "phone_number": f"+{suffix}333333",
        },
    )
    if _:
        delivery_user.set_password("password123")
        delivery_user.save()
        DeliveryPerson.objects.create(
            user=delivery_user, vehicle_type="motorcycle", vehicle_plate="ABC-123", is_active=True, status="approved"
        )

    return customer_user, vendor_user, delivery_user


def create_vendor_data(vendor_user):
    print("Creando datos de comercio y productos...")
    category, _ = VendorCategory.objects.get_or_create(
        name="Restaurantes", defaults={"description": "Comida preparada"}
    )

    vendor, _ = Vendor.objects.get_or_create(
        user=vendor_user,
        defaults={
            "business_name": "Burger King (Demo)",
            "description": "Hamburguesas y más",
            "category": category,
            "status": "approved",
            "is_open": True,
            "delivery_time": 30,
            "delivery_fee": 2.50,
        },
    )

    if _:
        Product.objects.create(vendor=vendor, name="Whopper", description="Hamburguesa clásica", price=5.00)
        Product.objects.create(vendor=vendor, name="Papas Fritas", description="Porción mediana", price=2.00)

    return vendor


def create_orders(customer_user, vendor_user, delivery_user):
    print("Creando pedidos...")
    customer = Customer.objects.get(user=customer_user)
    vendor = Vendor.objects.get(user=vendor_user)
    product = Product.objects.filter(vendor=vendor).first()

    if product and not Order.objects.filter(customer=customer).exists():
        order = Order.objects.create(
            customer=customer,
            vendor=vendor,
            total_amount=product.price + vendor.delivery_fee,
            delivery_fee=vendor.delivery_fee,
            status="pending",
            delivery_address="123 Main St",
        )
        OrderItem.objects.create(
            order=order, product=product, quantity=1, unit_price=product.price, subtotal=product.price
        )
        print("Pedido creado:", order.order_number)


if __name__ == "__main__":
    try:
        c, v, d = create_users()
        create_vendor_data(v)
        create_orders(c, v, d)
        print("¡Datos de prueba creados exitosamente!")
    except Exception as e:
        print("Error:", e)
