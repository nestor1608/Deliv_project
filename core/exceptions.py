# core/exceptions.py
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
import logging
import traceback

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """
    Handler personalizado para excepciones de la API
    Proporciona respuestas consistentes y logging de errores
    """
    
    # Obtener información del request
    request = context.get('request', None)
    view = context.get('view', None)
    
    # Log de la excepción
    if request:
        logger.error(f"API Exception in {request.method} {request.path}: {str(exc)}")
        logger.debug(f"Exception traceback: {traceback.format_exc()}")
    
    # Llamar al handler por defecto de DRF primero
    response = exception_handler(exc, context)
    
    # Si DRF no maneja la excepción, manejarla nosotros
    if response is None:
        response = handle_generic_error(exc, context)
    else:
        response = format_error_response(response, exc, context)
    
    return response

def handle_generic_error(exc, context):
    """Manejo de excepciones no manejadas por DRF"""
    
    if isinstance(exc, Http404):
        return Response({
            'error': 'not_found',
            'message': 'Recurso no encontrado',
            'details': str(exc) if str(exc) else 'El recurso solicitado no existe'
        }, status=status.HTTP_404_NOT_FOUND)
    
    elif isinstance(exc, PermissionDenied):
        return Response({
            'error': 'permission_denied',
            'message': 'Permisos insuficientes',
            'details': str(exc) if str(exc) else 'No tienes permisos para realizar esta acción'
        }, status=status.HTTP_403_FORBIDDEN)
    
    elif isinstance(exc, ValidationError):
        return Response({
            'error': 'validation_error',
            'message': 'Error de validación',
            'details': exc.messages if hasattr(exc, 'messages') else str(exc)
        }, status=status.HTTP_400_BAD_REQUEST)
    
    elif isinstance(exc, IntegrityError):
        return Response({
            'error': 'integrity_error',
            'message': 'Error de integridad de datos',
            'details': 'Los datos proporcionados violan las restricciones de la base de datos'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    else:
        # Error interno del servidor
        logger.error(f"Unhandled exception: {str(exc)}")
        logger.debug(traceback.format_exc())
        
        return Response({
            'error': 'internal_error',
            'message': 'Error interno del servidor',
            'details': 'Ha ocurrido un error inesperado. El equipo técnico ha sido notificado.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def format_error_response(response, exc, context):
    """Formatear respuestas de error para consistencia"""
    
    custom_response_data = {
        'error': get_error_code(response.status_code, exc),
        'message': get_user_friendly_message(response.status_code, exc),
    }
    
    # Agregar detalles específicos según el tipo de error
    if response.status_code == 400:
        # Errores de validación
        if hasattr(response.data, 'items'):
            custom_response_data['details'] = format_validation_errors(response.data)
        else:
            custom_response_data['details'] = response.data
    
    elif response.status_code == 401:
        custom_response_data['details'] = 'Token de autenticación inválido o expirado'
    
    elif response.status_code == 403:
        custom_response_data['details'] = 'No tienes permisos para realizar esta acción'
    
    elif response.status_code == 404:
        custom_response_data['details'] = 'El recurso solicitado no fue encontrado'
    
    elif response.status_code == 405:
        custom_response_data['details'] = 'Método HTTP no permitido para este endpoint'
    
    elif response.status_code == 429:
        custom_response_data['details'] = 'Límite de requests excedido. Intenta más tarde'
    
    elif response.status_code >= 500:
        custom_response_data['details'] = 'Error interno del servidor'
    
    else:
        custom_response_data['details'] = response.data
    
    response.data = custom_response_data
    return response

def get_error_code(status_code, exc):
    """Obtener código de error consistente"""
    error_codes = {
        400: 'bad_request',
        401: 'unauthorized',
        403: 'forbidden',
        404: 'not_found',
        405: 'method_not_allowed',
        429: 'too_many_requests',
        500: 'internal_error',
        502: 'bad_gateway',
        503: 'service_unavailable',
    }
    
    return error_codes.get(status_code, 'unknown_error')

def get_user_friendly_message(status_code, exc):
    """Obtener mensaje amigable para el usuario"""
    messages = {
        400: 'Datos inválidos',
        401: 'No autorizado',
        403: 'Acceso denegado',
        404: 'No encontrado',
        405: 'Método no permitido',
        429: 'Demasiadas solicitudes',
        500: 'Error del servidor',
        502: 'Error de conexión',
        503: 'Servicio no disponible',
    }
    
    return messages.get(status_code, 'Error desconocido')

def format_validation_errors(errors):
    """Formatear errores de validación de forma consistente"""
    if isinstance(errors, dict):
        formatted_errors = {}
        for field, field_errors in errors.items():
            if isinstance(field_errors, list):
                formatted_errors[field] = field_errors[0] if field_errors else 'Error de validación'
            else:
                formatted_errors[field] = str(field_errors)
        return formatted_errors
    elif isinstance(errors, list):
        return errors[0] if errors else 'Error de validación'
    else:
        return str(errors)

# core/handlers.py
from django.http import JsonResponse
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def handler404(request, exception):
    """Handler personalizado para errores 404"""
    
    # Para requests API, devolver JSON
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'not_found',
            'message': 'Endpoint no encontrado',
            'details': f'El endpoint {request.path} no existe'
        }, status=404)
    
    # Para requests web, redirigir a página 404 personalizada
    return JsonResponse({
        'error': 'page_not_found',
        'message': 'Página no encontrada'
    }, status=404)

def handler500(request):
    """Handler personalizado para errores 500"""
    
    logger.error(f"Server error 500 in {request.method} {request.path}")
    
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'internal_error',
            'message': 'Error interno del servidor',
            'details': 'Ha ocurrido un error inesperado. El equipo técnico ha sido notificado.'
        }, status=500)
    
    return JsonResponse({
        'error': 'server_error',
        'message': 'Error del servidor'
    }, status=500)

def handler403(request, exception):
    """Handler personalizado para errores 403"""
    
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'forbidden',
            'message': 'Acceso denegado',
            'details': 'No tienes permisos para acceder a este recurso'
        }, status=403)
    
    return JsonResponse({
        'error': 'access_denied',
        'message': 'Acceso denegado'
    }, status=403)

# core/validators.py
from django.core.exceptions import ValidationError
import re

def validate_phone_number(value):
    """Validador personalizado para números de teléfono"""
    phone_regex = re.compile(r'^\+?1?\d{9,15}$')
    if not phone_regex.match(value):
        raise ValidationError(
            'Formato de teléfono inválido. Debe incluir código de país y tener entre 9 y 15 dígitos.'
        )

def validate_username(value):
    """Validador personalizado para usernames"""
    if len(value) < 3:
        raise ValidationError('El nombre de usuario debe tener al menos 3 caracteres.')
    
    if len(value) > 30:
        raise ValidationError('El nombre de usuario no puede tener más de 30 caracteres.')
    
    username_regex = re.compile(r'^[a-zA-Z0-9._-]+$')
    if not username_regex.match(value):
        raise ValidationError(
            'El nombre de usuario solo puede contener letras, números, puntos, guiones y guiones bajos.'
        )

def validate_password_strength(password):
    """Validador de fortaleza de contraseña"""
    if len(password) < 8:
        raise ValidationError('La contraseña debe tener al menos 8 caracteres.')
    
    if not re.search(r'[A-Z]', password):
        raise ValidationError('La contraseña debe contener al menos una letra mayúscula.')
    
    if not re.search(r'[a-z]', password):
        raise ValidationError('La contraseña debe contener al menos una letra minúscula.')
    
    if not re.search(r'\d', password):
        raise ValidationError('La contraseña debe contener al menos un número.')
    
    # Opcional: validar caracteres especiales
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError('La contraseña debe contener al menos un carácter especial.')

def validate_file_size(file, max_size_mb=5):
    """Validador de tamaño de archivo"""
    max_size = max_size_mb * 1024 * 1024  # Convertir MB a bytes
    
    if file.size > max_size:
        raise ValidationError(f'El archivo no puede ser mayor a {max_size_mb}MB.')

def validate_image_format(file):
    """Validador de formato de imagen"""
    allowed_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    
    if file.content_type not in allowed_formats:
        raise ValidationError('Formato de imagen no válido. Usa JPG, PNG o WebP.')

# utils/response_helpers.py
from rest_framework.response import Response
from rest_framework import status

def success_response(data=None, message="Operación exitosa", status_code=status.HTTP_200_OK):
    """Helper para respuestas exitosas consistentes"""
    response_data = {
        'success': True,
        'message': message,
    }
    
    if data is not None:
        response_data['data'] = data
    
    return Response(response_data, status=status_code)

def error_response(message="Error en la operación", details=None, status_code=status.HTTP_400_BAD_REQUEST):
    """Helper para respuestas de error consistentes"""
    response_data = {
        'success': False,
        'error': get_error_code_simple(status_code),
        'message': message,
    }
    
    if details:
        response_data['details'] = details
    
    return Response(response_data, status=status_code)

def get_error_code_simple(status_code):
    """Obtener código de error basado en status HTTP"""
    error_codes = {
        400: 'bad_request',
        401: 'unauthorized',
        403: 'forbidden',
        404: 'not_found',
        429: 'too_many_requests',
        500: 'internal_error',
    }
    return error_codes.get(status_code, 'unknown_error')