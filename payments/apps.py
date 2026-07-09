from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"
    verbose_name = "Sistema de Pagos"

    def ready(self):
        import payments.signals  # noqa: F401
