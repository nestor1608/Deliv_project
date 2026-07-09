from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)
from .views import *

app_name = "users"

urlpatterns = [
    # Autenticación JWT (para móvil)
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # Autenticación tradicional (para web y móvil)
    path("register/", RegisterView.as_view(), name="register"),
    path("logout/", logout_view, name="logout"),
    # Perfil y gestión de usuario
    path("profile/", ProfileView.as_view(), name="profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    # Verificación de email/teléfono (opcional)
    # path('verify-email/', VerifyEmailView.as_view(), name='verify_email'),
    # path('verify-phone/', VerifyPhoneView.as_view(), name='verify_phone'),
    # Recuperación de contraseña
    path("password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("password-reset-confirm/<uidb64>/<token>/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
]
