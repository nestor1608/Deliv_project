from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Crear usuario administrador"

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, default="admin")
        parser.add_argument("--email", type=str, default="admin@delivst.com")
        parser.add_argument("--password", type=str, required=True, help="Admin password (required)")

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password = options["password"]

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Usuario {username} ya existe")
            return

        User.objects.create_superuser(
            username=username, email=email, password=password, role="admin", phone_number="+5493644000000"
        )

        self.stdout.write(self.style.SUCCESS(f"Superusuario creado: {username}"))
