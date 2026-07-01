# vendors/management/commands/create_sample_data.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from vendors.models import VendorCategory, Vendor, Product
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Crear datos de ejemplo para testing'
    
    def handle(self, *args, **options):
        # Crear categorías
        categories_data = [
            {'name': 'Restaurantes', 'description': 'Comida rápida y restaurantes'},
            {'name': 'Supermercados', 'description': 'Productos de almacén y supermercado'},
            {'name': 'Farmacias', 'description': 'Medicamentos y productos de salud'},
            {'name': 'Bebidas', 'description': 'Bebidas alcohólicas y sin alcohol'},
        ]
        
        for cat_data in categories_data:
            category, created = VendorCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults=cat_data
            )
            if created:
                self.stdout.write(f'Categoría creada: {category.name}')
        
        # Crear usuarios comercio de ejemplo
        vendors_data = [
            {
                'username': 'mcdonalds_st',
                'email': 'mcdonalds@test.com',
                'business_name': "McDonald's Santo Tomé",
                'category': 'Restaurantes',
                'address': 'Av. San Martín 1234, Santo Tomé',
                'latitude': -31.6625,
                'longitude': -60.7676,
            },
            {
                'username': 'super_vea',
                'email': 'vea@test.com',
                'business_name': 'Supermercado Vea',
                'category': 'Supermercados',
                'address': 'Calle Rivadavia 567, Santo Tomé',
                'latitude': -31.6635,
                'longitude': -60.7686,
            }
        ]
        
        for vendor_data in vendors_data:
            # Crear usuario
            user, created = User.objects.get_or_create(
                username=vendor_data['username'],
                defaults={
                    'email': vendor_data['email'],
                    'role': 'vendor',
                    'first_name': vendor_data['business_name'],
                    'phone_number': '+5493644123456',
                }
            )
            
            if created:
                user.set_password('password123')
                user.save()
                self.stdout.write(f'Usuario comercio creado: {user.username}')
                
                # Crear perfil de comercio
                category = VendorCategory.objects.get(name=vendor_data['category'])
                vendor = Vendor.objects.create(
                    user=user,
                    business_name=vendor_data['business_name'],
                    category=category,
                    address=vendor_data['address'],
                    latitude=vendor_data['latitude'],
                    longitude=vendor_data['longitude'],
                    business_license=f'LIC-{user.username.upper()}',
                    tax_id=f'TAX-{user.username.upper()}',
                    delivery_fee=Decimal('150.00'),
                    minimum_order=Decimal('500.00'),
                    delivery_time=30,
                    opening_time='08:00',
                    closing_time='23:00',
                    status='approved'
                )
                
                self.stdout.write(f'Comercio creado: {vendor.business_name}')
                
                # Crear productos de ejemplo
                if vendor_data['category'] == 'Restaurantes':
                    products = [
                        {'name': 'Big Mac', 'price': '890.00', 'category': 'Hamburguesas'},
                        {'name': 'McNuggets x6', 'price': '650.00', 'category': 'Pollo'},
                        {'name': 'Papas Grandes', 'price': '480.00', 'category': 'Acompañamientos'},
                        {'name': 'Coca Cola 500ml', 'price': '320.00', 'category': 'Bebidas'},
                    ]
                else:
                    products = [
                        {'name': 'Leche La Serenísima 1L', 'price': '450.00', 'category': 'Lácteos'},
                        {'name': 'Pan Lactal', 'price': '380.00', 'category': 'Panadería'},
                        {'name': 'Arroz Gallo 1kg', 'price': '520.00', 'category': 'Almacén'},
                    ]
                
                for prod_data in products:
                    Product.objects.create(
                        vendor=vendor,
                        name=prod_data['name'],
                        price=Decimal(prod_data['price']),
                        category=prod_data['category'],
                        stock=100,
                        is_available=True
                    )
                
                self.stdout.write(f'Productos creados para {vendor.business_name}')
