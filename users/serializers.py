from rest_framework import serializers
from .models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from django.db import models

from core.utils.lockout import check_lockout, record_failed_attempt, reset_attempts


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer para registro de usuarios"""

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "phone_number",
            "role",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError("Las contraseñas no coinciden")
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()

        # Create associated customer profile if role is customer
        role = validated_data.get("role", "customer")
        if role == "customer":
            from customers.models import Customer

            Customer.objects.get_or_create(user=user)

        return user


class UserSerializer(serializers.ModelSerializer):
    """Serializer para información básica del usuario"""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "role",
            "status",
            "profile_picture",
            "email_verified",
            "phone_verified",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "role"]


class LoginSerializer(TokenObtainPairSerializer):
    """Serializer para autenticación JWT que acepta username o email."""

    # Sobrescribir los campos por defecto
    username_field = "username_or_email"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remover el campo username por defecto y agregar el nuevo
        self.fields.pop("username", None)
        self.fields["username_or_email"] = serializers.CharField()
        self.fields["user_type"] = serializers.CharField()
        print(self.fields["user_type"])

    @classmethod
    def get_token(cls, user):
        """Obtener token JWT para el usuario"""
        return super().get_token(user)

    def validate(self, attrs):
        username_or_email = attrs.get("username_or_email")
        password = attrs.get("password")
        user_type = attrs.get("user_type")

        if not username_or_email:
            raise serializers.ValidationError({"username_or_email": "Este campo es requerido"})

        check_lockout(username_or_email)

        if not password:
            raise serializers.ValidationError({"password": "Este campo es requerido"})

        if not user_type:
            raise serializers.ValidationError({"user_type": "Este campo es requerido"})

        try:
            user = User.objects.filter(models.Q(username=username_or_email) | models.Q(email=username_or_email)).first()

            if not user:
                raise serializers.ValidationError(
                    {"non_field_errors": ["Usuario no encontrado"], "code": "user_not_found"}
                )

            if not user.check_password(password):
                raise serializers.ValidationError(
                    {"non_field_errors": ["Contraseña incorrecta"], "code": "invalid_password"}
                )

            if user.status != "active":
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [f"Cuenta {user.get_status_display().lower()}. Contacte al soporte"],
                        "code": "account_inactive",
                    }
                )

            if user.role != user_type:
                raise serializers.ValidationError(
                    {"non_field_errors": [f"No tiene permisos para acceder como {user_type}"], "code": "invalid_role"}
                )

            reset_attempts(username_or_email)

            refresh = self.get_token(user)
            return {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(user).data,
                "code": "login_success",
            }
        except (serializers.ValidationError, AuthenticationFailed):
            record_failed_attempt(username_or_email)
            raise


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(required=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError("Las contraseñas no coinciden")
        return attrs
