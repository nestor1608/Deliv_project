from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from delivery.models import DeliveryPerson

User = get_user_model()

class Command(BaseCommand):
    help = 'Crear repartidores de ejemplo'
    
    def handle(self, *args, **options):
        delivery_data = [
            {
                'username': 'repartidor1',
                'email': 'rep1@test.com',
                'first_name': 'Juan',
                'last_name': 'Pérez',
                'license_number': 'LIC001',
                'vehicle_type': 'Moto',
                'vehicle_plate': 'ABC123',
            },
            {
                'username': 'repartidor2',
                'email': 'rep2@test.com',
                'first_name': 'María',
                'last_name': 'González',
                'license_number': 'LIC002',
                'vehicle_type': 'Bicicleta',
                'vehicle_plate': 'BIC001',
            }
        ]
        
        for rep_data in delivery_data:
            user, created = User.objects.get_or_create(
                username=rep_data['username'],
                defaults={
                    'email': rep_data['email'],
                    'role': 'delivery',
                    'first_name': rep_data['first_name'],
                    'last_name': rep_data['last_name'],
                    'phone_number': f'+549364412{rep_data["username"][-1]}456',
                }
            )
            
            if created:
                user.set_password('password123')
                user.save()
                
                DeliveryPerson.objects.create(
                    user=user,
                    license_number=rep_data['license_number'],
                    vehicle_type=rep_data['vehicle_type'],
                    vehicle_plate=rep_data['vehicle_plate'],
                    status='approved',
                    availability='available',
                    current_latitude=-31.6625,
                    current_longitude=-60.7676
                )
                
                self.stdout.write(f'Repartidor creado: {user.get_full_name()}')