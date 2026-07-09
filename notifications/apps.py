from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "Sistema de Notificaciones"

    def ready(self):
        import notifications.signals  # noqa: F401
