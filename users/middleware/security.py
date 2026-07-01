# middleware/security.py
import logging
import json
from django.http import JsonResponse
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import re

logger = logging.getLogger(__name__)

class SecurityMiddleware:
    """Middleware de seguridad personalizado para la API"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Patrones de endpoints sensibles
        self.sensitive_endpoints = [
            r'/api/auth/token/',
            r'/api/auth/register/',
            r'/api/auth/password-reset/',
        ]
        
        # Rate limits por endpoint
        self.rate_limits = {
            '/api/auth/token/': {'requests': 5, 'window': 300},  # 5 req/5min
            '/api/auth/register/': {'requests': 3, 'window': 600},  # 3 req/10min
            '/api/auth/password-reset/': {'requests': 2, 'window': 300},  # 2 req/5min
        }

    def __call__(self, request):
        # Aplicar validaciones de seguridad
        security_response = self.check_security(request)
        if security_response:
            return security_response
            
        response = self.get_response(request)
        
        # Headers de seguridad
        self.add_security_headers(request, response)
        
        return response

    def check_security(self, request):
        """Verificaciones de seguridad principales"""
        
        # 1. Verificar rate limiting
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        # 2. Verificar contenido malicioso
        malicious_response = self.check_malicious_content(request)
        if malicious_response:
            return malicious_response
        
        # 3. Validar tamaño del payload
        size_response = self.check_payload_size(request)
        if size_response:
            return size_response
            
        return None

    def check_rate_limit(self, request):
        """Rate limiting basado en IP y endpoint"""
        ip = self.get_client_ip(request)
        path = request.path
        
        # Verificar si el endpoint tiene rate limiting
        for endpoint, limits in self.rate_limits.items():
            if path.startswith(endpoint):
                cache_key = f"rate_limit_{endpoint}_{ip}"
                current_requests = cache.get(cache_key, 0)
                
                if current_requests >= limits['requests']:
                    logger.warning(f"Rate limit exceeded for IP {ip} on {endpoint}")
                    return JsonResponse({
                        'detail': 'Demasiadas solicitudes. Intenta más tarde.'
                    }, status=429)
                
                # Incrementar contador
                cache.set(cache_key, current_requests + 1, limits['window'])
                
        return None

    def check_malicious_content(self, request):
        """Detectar contenido potencialmente malicioso"""
        try:
            # Patrones sospechosos en URLs
            suspicious_patterns = [
                r'<script',
                r'javascript:',
                r'union\s+select',
                r'drop\s+table',
                r'\.\./',
                r'exec\s*\(',
            ]
            
            # Verificar path
            for pattern in suspicious_patterns:
                if re.search(pattern, request.path, re.IGNORECASE):
                    logger.error(f"Malicious pattern detected in path: {request.path}")
                    return JsonResponse({
                        'detail': 'Solicitud no válida'
                    }, status=400)
            
            # Verificar parámetros GET
            for key, value in request.GET.items():
                for pattern in suspicious_patterns:
                    if re.search(pattern, str(value), re.IGNORECASE):
                        logger.error(f"Malicious pattern in GET param {key}: {value}")
                        return JsonResponse({
                            'detail': 'Parámetros no válidos'
                        }, status=400)
            
            # Verificar body para requests POST/PUT/PATCH
            if request.method in ['POST', 'PUT', 'PATCH'] and hasattr(request, 'body'):
                try:
                    body_str = request.body.decode('utf-8')
                    for pattern in suspicious_patterns:
                        if re.search(pattern, body_str, re.IGNORECASE):
                            logger.error(f"Malicious pattern in body from IP {self.get_client_ip(request)}")
                            return JsonResponse({
                                'detail': 'Contenido no válido'
                            }, status=400)
                except UnicodeDecodeError:
                    # Si no se puede decodificar, podría ser sospechoso
                    logger.warning(f"Unable to decode request body from IP {self.get_client_ip(request)}")
                    
        except Exception as e:
            logger.error(f"Error checking malicious content: {str(e)}")
            
        return None

    def check_payload_size(self, request):
        """Verificar tamaño del payload"""
        max_size = getattr(settings, 'MAX_REQUEST_SIZE', 10 * 1024 * 1024)  # 10MB por defecto
        
        if hasattr(request, 'body') and len(request.body) > max_size:
            logger.warning(f"Payload too large from IP {self.get_client_ip(request)}: {len(request.body)} bytes")
            return JsonResponse({
                'detail': 'Payload demasiado grande'
            }, status=413)
            
        return None

    def get_client_ip(self, request):
        """Obtener IP real del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip

    def add_security_headers(self, request, response):
        """Agregar headers de seguridad"""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # HSTS solo en producción con HTTPS
        if not settings.DEBUG and request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

class RequestLoggingMiddleware:
    """Middleware para logging de requests API"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = timezone.now()
        
        # Log del request
        if request.path.startswith('/api/'):
            logger.info(f"API Request: {request.method} {request.path} from {self.get_client_ip(request)}")
        
        response = self.get_response(request)
        
        # Log del response
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds() * 1000  # en millisegundos
        
        if request.path.startswith('/api/'):
            logger.info(f"API Response: {response.status_code} in {duration:.2f}ms")
            
            # Log de errores detallado
            if response.status_code >= 400:
                logger.warning(f"API Error {response.status_code}: {request.method} {request.path}")
        
        return response
        
    def get_client_ip(self, request):
        """Obtener IP real del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip

class CORSSecurityMiddleware:
    """Middleware CORS personalizado con validaciones de seguridad"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
        
    def __call__(self, request):
        response = self.get_response(request)
        
        # Aplicar CORS solo a endpoints API
        if request.path.startswith('/api/'):
            self.add_cors_headers(request, response)
            
        return response
    
    def add_cors_headers(self, request, response):
        """Agregar headers CORS de forma segura"""
        origin = request.META.get('HTTP_ORIGIN')
        
        # En desarrollo, permitir localhost
        if settings.DEBUG and origin and ('localhost' in origin or '127.0.0.1' in origin):
            response['Access-Control-Allow-Origin'] = origin
        elif origin in self.allowed_origins:
            response['Access-Control-Allow-Origin'] = origin
        
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, X-Requested-With'
        response['Access-Control-Allow-Credentials'] = 'true'
        response['Access-Control-Max-Age'] = '86400'  # 24 horas