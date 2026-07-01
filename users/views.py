from rest_framework import status, generics, permissions, serializers
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.contrib.auth import get_user_model, logout as auth_logout
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
import logging
import json
from .serializers import (
    UserRegistrationSerializer, 
    UserSerializer, 
    LoginSerializer,
    ChangePasswordSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

# Configurar logging
logger = logging.getLogger(__name__)

User = get_user_model()

class LoginRateThrottle(AnonRateThrottle):
    """Rate limiting específico para login"""
    rate = '5/min'  # 5 intentos por minuto

class RegisterRateThrottle(AnonRateThrottle):
    """Rate limiting para registro"""
    rate = '3/min'  # 3 registros por minuto

@method_decorator(never_cache, name='dispatch')
class RegisterView(generics.CreateAPIView):
    """Vista para registro de nuevos usuarios con validaciones mejoradas"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]
    
    @extend_schema(
        summary='Registro de usuario',
        description='Registra un nuevo usuario en el sistema. Crea el usuario, genera tokens JWT y retorna los datos del perfil creado.',
        request=UserRegistrationSerializer,
        responses={
            201: OpenApiResponse(response=UserSerializer, description='Usuario registrado exitosamente con tokens JWT'),
            400: OpenApiResponse(description='Error de validación - datos inválidos o usuario ya existe'),
        },
        tags=['auth'],
        examples=[
            OpenApiExample(
                'Registro exitoso',
                summary='Ejemplo de registro',
                description='Ejemplo de una solicitud de registro exitosa',
                value={
                    'username': 'nuevo_usuario',
                    'email': 'usuario@ejemplo.com',
                    'password': 'contraseña123',
                    'password_confirm': 'contraseña123',
                    'first_name': 'Juan',
                    'last_name': 'Pérez',
                    'role': 'customer',
                },
                request_only=True,
            ),
        ],
    )
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                
                # Verificar si el usuario ya existe
                username = serializer.validated_data.get('username')
                email = serializer.validated_data.get('email')
                
                if User.objects.filter(username__iexact=username).exists():
                    return Response({
                        'username': ['Este nombre de usuario ya está en uso.']
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if User.objects.filter(email__iexact=email).exists():
                    return Response({
                        'email': ['Este email ya está registrado.']
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                user = serializer.save()
                
                # Generar tokens JWT
                refresh = RefreshToken.for_user(user)
                
                # Log del registro exitoso
                logger.info(f"Usuario registrado exitosamente: {user.username} ({user.email})")
                
                return Response({
                    'user': UserSerializer(user).data,
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'message': 'Usuario registrado exitosamente'
                }, status=status.HTTP_201_CREATED)
                
        except serializers.ValidationError:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error en registro de usuario: {str(e)}")
            return Response({
                'detail': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(never_cache, name='dispatch')
class CustomTokenObtainPairView(TokenObtainPairView):
    """Vista personalizada para login con rate limiting y logging"""
    serializer_class = LoginSerializer
    throttle_classes = [LoginRateThrottle]
    
    @extend_schema(
        summary='Inicio de sesión',
        description='Autentica un usuario usando nombre de usuario o email y contraseña. Retorna tokens JWT (access y refresh) junto con los datos del usuario. Valida el rol del usuario para control de acceso.',
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(description='Autenticación exitosa - retorna tokens JWT y datos del usuario'),
            400: OpenApiResponse(description='Error de autenticación - credenciales inválidas, cuenta inactiva o rol incorrecto'),
        },
        tags=['auth'],
        examples=[
            OpenApiExample(
                'Login exitoso',
                summary='Ejemplo de inicio de sesión',
                description='Ejemplo de una solicitud de inicio de sesión exitosa',
                value={
                    'username_or_email': 'usuario@ejemplo.com',
                    'password': 'contraseña123',
                    'user_type': 'customer',
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            
            try:
                serializer.is_valid(raise_exception=True)
                return Response(serializer.validated_data, status=status.HTTP_200_OK)
                
            except serializers.ValidationError as e:
                error_data = e.detail
                error_code = error_data.get('code', 'validation_error')
                
                # Log del error específico
                logger.warning(f"Error de login: {error_code} - {error_data}")
                
                return Response({
                    'error': error_data.get('non_field_errors', ['Error de validación']),
                    'code': error_code,
                    'details': error_data
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error interno en login: {str(e)}")
            return Response({
                'error': 'Error interno del servidor',
                'code': 'server_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema_view(
    get=extend_schema(
        summary='Obtener perfil de usuario',
        description='Retorna los datos del perfil del usuario autenticado.',
        responses={200: UserSerializer},
        tags=['auth'],
    ),
    put=extend_schema(
        summary='Actualizar perfil de usuario (completo)',
        description='Actualiza todos los datos del perfil del usuario autenticado. No permite modificar campos críticos como username, role o status.',
        request=UserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description='Error de validación o campo restringido'),
        },
        tags=['auth'],
    ),
    patch=extend_schema(
        summary='Actualizar perfil de usuario (parcial)',
        description='Actualiza parcialmente los datos del perfil del usuario autenticado. No permite modificar campos críticos como username, role o status.',
        request=UserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description='Error de validación o campo restringido'),
        },
        tags=['auth'],
    ),
)
class ProfileView(generics.RetrieveUpdateAPIView):
    """Vista para ver y actualizar perfil de usuario"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            
            # No permitir cambio de campos críticos
            restricted_fields = ['username', 'role', 'status', 'id']
            for field in restricted_fields:
                if field in request.data:
                    return Response({
                        'detail': f'No se puede modificar el campo {field}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            logger.info(f"Perfil actualizado: {instance.username}")
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error actualizando perfil: {str(e)}")
            return Response({
                'detail': 'Error actualizando perfil'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([UserRateThrottle])
def logout_view(request):
    """Vista mejorada para cerrar sesión con invalidación de tokens"""
    try:
        refresh_token = request.data.get('refresh_token')
        
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
                logger.info(f"Token invalidado para usuario: {request.user.username}")
            except TokenError:
                logger.warning(f"Token inválido en logout: {request.user.username}")
        
        # Logout tradicional de Django
        auth_logout(request)
        
        # Limpiar caché del usuario si se usa
        cache.delete(f"user_data_{request.user.id}")
        
        return Response({
            "detail": "Sesión cerrada correctamente"
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error en logout: {str(e)}")
        return Response({
            "detail": "Error cerrando sesión"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ChangePasswordView(generics.UpdateAPIView):
    """Vista mejorada para cambiar contraseña"""
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_object(self):
        return self.request.user

    @extend_schema(
        summary='Cambiar contraseña',
        description='Permite al usuario autenticado cambiar su contraseña. Requiere la contraseña actual y verifica que la nueva sea diferente a la anterior.',
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description='Contraseña actualizada correctamente'),
            400: OpenApiResponse(description='Error de validación - contraseña actual incorrecta o nueva contraseña inválida'),
        },
        tags=['auth'],
    )
    def update(self, request, *args, **kwargs):
        try:
            user = self.get_object()
            serializer = self.get_serializer(data=request.data)
            
            if serializer.is_valid():
                old_password = serializer.validated_data.get('old_password')
                new_password = serializer.validated_data.get('new_password')
                
                # Verificar contraseña actual
                if not user.check_password(old_password):
                    logger.warning(f"Intento de cambio de contraseña con contraseña incorrecta: {user.username}")
                    return Response({
                        "old_password": ["Contraseña actual incorrecta."]
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Verificar que la nueva contraseña sea diferente
                if user.check_password(new_password):
                    return Response({
                        "new_password": ["La nueva contraseña debe ser diferente a la actual."]
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Cambiar contraseña
                user.set_password(new_password)
                user.save(update_fields=['password'])
                
                logger.info(f"Contraseña cambiada exitosamente: {user.username}")
                
                return Response({
                    "detail": "Contraseña actualizada correctamente"
                }, status=status.HTTP_200_OK)
                
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error cambiando contraseña: {str(e)}")
            return Response({
                'detail': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PasswordResetRequestView(generics.GenericAPIView):
    """Vista para solicitar reseteo de contraseña con rate limiting"""
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]

    @extend_schema(
        summary='Solicitar restablecimiento de contraseña',
        description='Envía un email con un enlace para restablecer la contraseña. Incluye rate limiting por email (5 minutos entre solicitudes). Por seguridad, siempre retorna el mismo mensaje independientemente de si el email existe.',
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(description='Mensaje genérico indicando que si el email existe, se enviará el enlace de recuperación'),
            429: OpenApiResponse(description='Demasiadas solicitudes - ya se envió un enlace recientemente. Espera 5 minutos.'),
        },
        tags=['auth'],
        examples=[
            OpenApiExample(
                'Solicitud de recuperación',
                summary='Ejemplo de solicitud',
                description='Ejemplo de una solicitud de restablecimiento de contraseña',
                value={
                    'email': 'usuario@ejemplo.com',
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            email = serializer.validated_data['email'].lower()
            
            # Siempre responder igual por seguridad
            response_message = "Si existe una cuenta con este email, recibirás un enlace de recuperación."
            
            try:
                user = User.objects.get(email__iexact=email, status='active')
                
                # Rate limiting por email
                cache_key = f"password_reset_{email}"
                if cache.get(cache_key):
                    return Response({
                        "detail": "Ya se envió un enlace recientemente. Espera 5 minutos."
                    }, status=status.HTTP_429_TOO_MANY_REQUESTS)
                
                # Generar token y enviar email
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                reset_url = f"{getattr(settings, 'FRONTEND_URL', '')}/password-reset-confirm/{uid}/{token}/"
                
                # Enviar email (en producción usar Celery para tareas asíncronas)
                try:
                    send_mail(
                        'Restablecer contraseña - Dely',
                        f'Hola {user.first_name or user.username},\n\n'
                        f'Recibimos una solicitud para restablecer la contraseña de tu cuenta.\n'
                        f'Haz clic en el siguiente enlace para crear una nueva contraseña:\n\n'
                        f'{reset_url}\n\n'
                        f'Este enlace expirará en 24 horas.\n\n'
                        f'Si no solicitaste este cambio, ignora este email.\n\n'
                        f'Equipo Dely',
                        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@dely.com'),
                        [email],
                        fail_silently=False,
                    )
                    
                    # Marcar en caché para rate limiting
                    cache.set(cache_key, True, 300)  # 5 minutos
                    
                    logger.info(f"Email de recuperación enviado a: {email}")
                    
                except Exception as email_error:
                    logger.error(f"Error enviando email de recuperación: {str(email_error)}")
                    
            except User.DoesNotExist:
                logger.info(f"Intento de recuperación para email no existente: {email}")
            
            return Response({
                "detail": response_message
            }, status=status.HTTP_200_OK)
            
        except serializers.ValidationError:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error en solicitud de recuperación: {str(e)}")
            return Response({
                'detail': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PasswordResetConfirmView(generics.GenericAPIView):
    """Vista para confirmar reseteo de contraseña"""
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]

    @extend_schema(
        summary='Confirmar restablecimiento de contraseña',
        description='Confirma el restablecimiento de contraseña usando el UID y token enviados por email. Valida que el enlace sea válido y no haya expirado.',
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description='Contraseña restablecida correctamente'),
            400: OpenApiResponse(description='Enlace inválido o expirado - el UID o token no son válidos'),
        },
        tags=['auth'],
    )
    def post(self, request, uidb64, token):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            try:
                uid = urlsafe_base64_decode(uidb64).decode()
                user = User.objects.get(pk=uid, status='active')
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                logger.warning(f"Intento de reset con UID inválido: {uidb64}")
                return Response({
                    "detail": "Enlace inválido o expirado"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if user is not None and default_token_generator.check_token(user, token):
                new_password = serializer.validated_data['new_password']
                user.set_password(new_password)
                user.save(update_fields=['password'])
                
                logger.info(f"Contraseña restablecida exitosamente: {user.username}")
                
                return Response({
                    "detail": "Contraseña restablecida correctamente"
                }, status=status.HTTP_200_OK)
            
            logger.warning(f"Intento de reset con token inválido para usuario: {user.username if user else 'unknown'}")
            return Response({
                "detail": "Enlace inválido o expirado"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except serializers.ValidationError:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error en confirmación de reset: {str(e)}")
            return Response({
                'detail': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)