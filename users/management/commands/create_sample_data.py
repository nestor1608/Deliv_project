from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from customers.models import Customer, CustomerAddress
from vendors.models import Vendor, Product, VendorCategory
from orders.models import Order, OrderItem
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Crea datos de prueba para la aplicación'
    
    def handle(self, *args, **options):
        self.stdout.write('Creando datos de prueba...')
        
        # Verificar y crear usuarios solo si no existen
        customer_user, _ = User.objects.get_or_create(
            username='cliente1',
            defaults={
                'email': 'cliente@example.com',
                'first_name': 'Juan',
                'last_name': 'Pérez',
                'phone_number': '+5493644123456',
                'role': 'customer'
            }
        )
        customer_user.set_password('test123')
        customer_user.save()
        
        vendor_user, _ = User.objects.get_or_create(
            username='comercio1',
            defaults={
                'email': 'comercio@example.com',
                'first_name': 'María',
                'last_name': 'González',
                'phone_number': '+5493644123457',
                'role': 'vendor'
            }
        )
        vendor_user.set_password('test123')
        vendor_user.save()
        
        delivery_user, _ = User.objects.get_or_create(
            username='repartidor1',
            defaults={
                'email': 'repartidor@example.com',
                'first_name': 'Carlos',
                'last_name': 'Rodríguez',
                'phone_number': '+5493644123458',
                'role': 'delivery'
            }
        )
        delivery_user.set_password('test123')
        delivery_user.save()
        
        # Crear o obtener categoría de comercio
        category, _ = VendorCategory.objects.get_or_create(
            name='Restaurante',
            defaults={'description': 'Restaurantes y pizzerías'}
        )
        
        # Crear perfiles
        customer, _ = Customer.objects.get_or_create(
            user=customer_user,
            defaults={'loyalty_points': 500}
        )
        
        vendor, _ = Vendor.objects.get_or_create(
            user=vendor_user,
            defaults={
                'business_name': 'Pizzería Don Juan',
                'description': 'Las mejores pizzas de la ciudad',
                'category': category,
                'business_license': 'LIC-123456',
                'tax_id': '30-12345678-9',
                'address': 'Av. Principal 1000',
                'latitude': -34.603722,
                'longitude': -58.381592,
                'delivery_fee': Decimal('300.00'),
                'minimum_order': Decimal('1000.00'),
                'opening_time': '10:00',
                'closing_time': '23:00'
            }
        )
        
        # Crear dirección del cliente
        CustomerAddress.objects.get_or_create(
            customer=customer,
            label='Casa',
            defaults={
                'street_address': 'Av. San Martín 1234',
                'city': 'Santo Tomé',
                'state': 'Corrientes',
                'postal_code': '3016',
                'is_default': True
            }
        )
        
        # Datos de productos
        products_data = [
            {
                'name': 'Pizza Margherita',
                'description': 'Pizza con salsa de tomate, mozzarella y albahaca',
                'price': Decimal('1500.00'),
                'category': 'Pizza',
                'stock': 50,
                'is_available': True
            },
            {
                'name': 'Pizza Pepperoni',
                'description': 'Pizza con pepperoni y mozzarella',
                'price': Decimal('1800.00'),
                'category': 'Pizza',
                'stock': 40,
                'is_available': True
            },
            {
                'name': 'Empanadas de Carne',
                'description': 'Empanadas caseras de carne (docena)',
                'price': Decimal('2400.00'),
                'category': 'Empanadas',
                'stock': 30,
                'is_available': True
            }
        ]
        
        # Crear productos
        products = []
        for product_data in products_data:
            product, created = Product.objects.get_or_create(
                vendor=vendor,
                name=product_data['name'],
                defaults=product_data
            )
            products.append(product)
            if created:
                self.stdout.write(f'Producto creado: {product.name}')
        
        # Crear pedido de ejemplo
        order, created = Order.objects.get_or_create(
            customer=customer,
            vendor=vendor,
            defaults={
                'delivery_address': 'Av. San Martín 1234, Santo Tomé, Corrientes',
                'delivery_latitude': -34.603722,
                'delivery_longitude': -58.381592,
                'subtotal': Decimal('3300.00'),
                'delivery_fee': Decimal('300.00'),
                'tax_amount': Decimal('693.00'),
                'total_amount': Decimal('4293.00'),
                'status': 'confirmed'
            }
        )
        
        if created:
            # Crear items del pedido
            OrderItem.objects.get_or_create(
                order=order,
                product=products[0],  # Pizza Margherita
                defaults={
                    'quantity': 1,
                    'unit_price': products[0].price,
                    'total_price': products[0].price
                }
            )
            
            OrderItem.objects.get_or_create(
                order=order,
                product=products[1],  # Pizza Pepperoni
                defaults={
                    'quantity': 1,
                    'unit_price': products[1].price,
                    'total_price': products[1].price
                }
            )
            
            self.stdout.write(f'Pedido creado: #{order.id}')
        
        self.stdout.write(
            self.style.SUCCESS('\nDatos de prueba creados/actualizados exitosamente!')
        )
        self.stdout.write(f'\nCredenciales de prueba:')
        self.stdout.write(f'Cliente: {customer_user.username} / test123')
        self.stdout.write(f'Comercio: {vendor_user.username} / test123')
        self.stdout.write(f'Repartidor: {delivery_user.username} / test123')