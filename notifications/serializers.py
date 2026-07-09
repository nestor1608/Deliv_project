from rest_framework import serializers
from .models import Notification, NotificationType, UserDevice
from django.contrib.auth import get_user_model

User = get_user_model()


class NotificationTypeSerializer(serializers.ModelSerializer):
    """Serializer para tipos de notificaciones"""

    class Meta:
        model = NotificationType
        fields = ["id", "name", "description", "template_title", "template_body", "is_active"]


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer para notificaciones"""

    notification_type_info = NotificationTypeSerializer(source="notification_type", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type_info",
            "title",
            "body",
            "data",
            "status",
            "status_display",
            "time_ago",
            "created_at",
            "sent_at",
            "read_at",
        ]
        read_only_fields = ["id", "notification_type_info", "status_display", "time_ago", "created_at", "sent_at"]

    def get_time_ago(self, obj):
        """Calcular tiempo transcurrido desde la creación"""
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        diff = now - obj.created_at

        if diff < timedelta(minutes=1):
            return "Hace menos de 1 minuto"
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() // 60)
            return f"Hace {minutes} minuto{'s' if minutes != 1 else ''}"
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() // 3600)
            return f"Hace {hours} hora{'s' if hours != 1 else ''}"
        elif diff < timedelta(days=7):
            days = diff.days
            return f"Hace {days} día{'s' if days != 1 else ''}"
        else:
            return obj.created_at.strftime("%d/%m/%Y")


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear notificaciones"""

    user_id = serializers.IntegerField(write_only=True)
    notification_type_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Notification
        fields = ["user_id", "notification_type_id", "title", "body", "data"]

    def validate_user_id(self, value):
        try:
            User.objects.get(id=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Usuario no existe")

    def validate_notification_type_id(self, value):
        try:
            NotificationType.objects.get(id=value, is_active=True)
            return value
        except NotificationType.DoesNotExist:
            raise serializers.ValidationError("Tipo de notificación no existe o está inactivo")

    def create(self, validated_data):
        user_id = validated_data.pop("user_id")
        notification_type_id = validated_data.pop("notification_type_id")

        user = User.objects.get(id=user_id)
        notification_type = NotificationType.objects.get(id=notification_type_id)

        return Notification.objects.create(user=user, notification_type=notification_type, **validated_data)


class UserDeviceSerializer(serializers.ModelSerializer):
    """Serializer para dispositivos de usuario"""

    platform_display = serializers.CharField(source="get_platform_display", read_only=True)

    class Meta:
        model = UserDevice
        fields = [
            "id",
            "fcm_token",
            "platform",
            "platform_display",
            "device_id",
            "app_version",
            "is_active",
            "created_at",
            "last_used",
        ]
        read_only_fields = ["id", "platform_display", "created_at", "last_used"]


class UserDeviceCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear/actualizar dispositivos"""

    class Meta:
        model = UserDevice
        fields = ["fcm_token", "platform", "device_id", "app_version"]

    def validate_fcm_token(self, value):
        """Validar que el token FCM tenga formato válido"""
        if len(value) < 10:
            raise serializers.ValidationError("Token FCM inválido")
        return value

    def create(self, validated_data):
        # Desactivar tokens anteriores del mismo dispositivo
        device_id = validated_data.get("device_id")
        if device_id:
            UserDevice.objects.filter(user=self.context["request"].user, device_id=device_id).update(is_active=False)

        return super().create(validated_data)


class BulkNotificationSerializer(serializers.Serializer):
    """Serializer para notificaciones masivas"""

    title = serializers.CharField(max_length=200)
    body = serializers.CharField()
    user_roles = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                ("customer", "Cliente"),
                ("vendor", "Comercio"),
                ("delivery", "Repartidor"),
                ("admin", "Administrador"),
            ]
        ),
        required=False,
        allow_empty=True,
    )
    user_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    data = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        user_roles = attrs.get("user_roles", [])
        user_ids = attrs.get("user_ids", [])

        if not user_roles and not user_ids:
            raise serializers.ValidationError("Debe especificar al menos user_roles o user_ids")

        return attrs


class NotificationStatsSerializer(serializers.Serializer):
    """Serializer para estadísticas de notificaciones"""

    total = serializers.IntegerField()
    unread = serializers.IntegerField()
    read = serializers.IntegerField()
    failed = serializers.IntegerField()
    today = serializers.IntegerField()
    this_week = serializers.IntegerField()
    by_type = serializers.ListSerializer(child=serializers.DictField(), read_only=True)
