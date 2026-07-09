from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from mobility.models import Driver

User = get_user_model()


class Command(BaseCommand):
    help = "Crear conductores de ejemplo"

    def handle(self, *args, **options):
        drivers_data = [
            {
                "username": "conductor1",
                "email": "cond1@test.com",
                "first_name": "Carlos",
                "last_name": "Rodríguez",
                "license_number": "DRV001",
                "vehicle_type": "car",
                "vehicle_brand": "Toyota",
                "vehicle_model": "Corolla",
                "vehicle_year": 2020,
                "vehicle_plate": "CAR123",
                "vehicle_color": "Blanco",
            },
            {
                "username": "conductor2",
                "email": "cond2@test.com",
                "first_name": "Ana",
                "last_name": "Martínez",
                "license_number": "DRV002",
                "vehicle_type": "car",
                "vehicle_brand": "Chevrolet",
                "vehicle_model": "Prisma",
                "vehicle_year": 2019,
                "vehicle_plate": "CAR456",
                "vehicle_color": "Gris",
            },
        ]

        for driver_data in drivers_data:
            user, created = User.objects.get_or_create(
                username=driver_data["username"],
                defaults={
                    "email": driver_data["email"],
                    "role": "delivery",  # Nota: usar 'delivery' para conductores también
                    "first_name": driver_data["first_name"],
                    "last_name": driver_data["last_name"],
                    "phone_number": f'+549364412{driver_data["username"][-1]}789',
                },
            )

            if created:
                user.set_password("password123")
                user.save()

                Driver.objects.create(
                    user=user,
                    license_number=driver_data["license_number"],
                    vehicle_type=driver_data["vehicle_type"],
                    vehicle_brand=driver_data["vehicle_brand"],
                    vehicle_model=driver_data["vehicle_model"],
                    vehicle_year=driver_data["vehicle_year"],
                    vehicle_plate=driver_data["vehicle_plate"],
                    vehicle_color=driver_data["vehicle_color"],
                    status="approved",
                    availability="available",
                    current_latitude=-31.6625,
                    current_longitude=-60.7676,
                )

                self.stdout.write(f"Conductor creado: {user.get_full_name()}")
