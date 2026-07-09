from django.apps import AppConfig


class MobilityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mobility"
    verbose_name = "Sistema de Movilidad"

    def ready(self):
        import mobility.signals  # noqa: F401
