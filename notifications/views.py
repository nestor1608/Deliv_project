from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import Notification, NotificationType, UserDevice
from .serializers import (
    NotificationSerializer, NotificationCreateSerializer,
    UserDeviceSerializer, UserDeviceCreateSerializer,
    NotificationTypeSerializer, BulkNotificationSerializer
)
from core.utils.notifications import FCMService
from core.tasks import send_push_notification

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

@extend_schema_view(
    list=extend_schema(
        summary='Listar notificaciones',
        description='Obtiene la lista de notificaciones del usuario autenticado.',
        tags=['notifications'],
    ),
    create=extend_schema(
        summary='Crear notificación',
        description='Crea una nueva notificación (solo administradores).',
        tags=['notifications'],
    ),
    retrieve=extend_schema(
        summary='Obtener notificación',
        description='Obtiene los detalles de una notificación específica.',
        tags=['notifications'],
    ),
)
class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet para notificaciones de usuarios
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'notification_type']
    search_fields = ['title', 'body']
    ordering_fields = ['created_at', 'sent_at', 'read_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        # Los usuarios solo ven sus propias notificaciones
        return Notification.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return NotificationCreateSerializer
        return NotificationSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            # Solo admins pueden crear notificaciones directamente
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @extend_schema(
        summary='Marcar como leída',
        description='Marca una notificación específica como leída.',
        tags=['notifications'],
        responses={200: OpenApiResponse(description='Notificación marcada como leída')},
    )
    @action(detail=True, methods=['patch'])
    def mark_as_read(self, request, pk=None):
        """Marcar notificación como leída"""
        notification = self.get_object()
        
        if notification.status != 'read':
            notification.status = 'read'
            notification.read_at = timezone.now()
            notification.save()
        
        return Response({
            'message': 'Notificación marcada como leída',
            'notification': NotificationSerializer(notification).data
        })
    
    @extend_schema(
        summary='Marcar todas como leídas',
        description='Marca todas las notificaciones no leídas del usuario como leídas.',
        tags=['notifications'],
        responses={200: OpenApiResponse(description='Notificaciones marcadas como leídas')},
    )
    @action(detail=False, methods=['patch'])
    def mark_all_read(self, request):
        """Marcar todas las notificaciones como leídas"""
        unread_notifications = Notification.objects.filter(
            user=request.user,
            status__in=['pending', 'sent', 'delivered']
        )
        
        count = unread_notifications.update(
            status='read',
            read_at=timezone.now()
        )
        
        return Response({
            'message': f'{count} notificaciones marcadas como leídas'
        })
    
    @extend_schema(
        summary='Contar no leídas',
        description='Obtiene la cantidad de notificaciones no leídas del usuario.',
        tags=['notifications'],
        responses={200: OpenApiResponse(description='Cantidad de notificaciones no leídas')},
    )
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Obtener cantidad de notificaciones no leídas"""
        count = Notification.objects.filter(
            user=request.user,
            status__in=['pending', 'sent', 'delivered']
        ).count()
        
        return Response({'unread_count': count})
    
    @extend_schema(
        summary='Eliminar notificaciones antiguas',
        description='Elimina las notificaciones leídas con más de 30 días de antigüedad.',
        tags=['notifications'],
        responses={200: OpenApiResponse(description='Notificaciones antiguas eliminadas')},
    )
    @action(detail=False, methods=['delete'])
    def clear_old(self, request):
        """Eliminar notificaciones leídas antiguas (más de 30 días)"""
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=30)
        
        deleted_count, _ = Notification.objects.filter(
            user=request.user,
            status='read',
            read_at__lt=cutoff_date
        ).delete()
        
        return Response({
            'message': f'{deleted_count} notificaciones antiguas eliminadas'
        })

@extend_schema_view(
    list=extend_schema(
        summary='Listar dispositivos',
        description='Obtiene la lista de dispositivos registrados del usuario.',
        tags=['notifications'],
    ),
    create=extend_schema(
        summary='Registrar dispositivo',
        description='Registra un nuevo dispositivo FCM para el usuario.',
        tags=['notifications'],
    ),
    retrieve=extend_schema(
        summary='Obtener dispositivo',
        description='Obtiene los detalles de un dispositivo específico.',
        tags=['notifications'],
    ),
)
class UserDeviceViewSet(viewsets.ModelViewSet):
    """
    ViewSet para dispositivos de usuario (tokens FCM)
    """
    serializer_class = UserDeviceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['platform', 'is_active']
    
    def get_queryset(self):
        return UserDevice.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return UserDeviceCreateSerializer
        return UserDeviceSerializer
    
    def perform_create(self, serializer):
        # Desactivar dispositivos anteriores con el mismo device_id
        device_id = serializer.validated_data.get('device_id')
        if device_id:
            UserDevice.objects.filter(
                user=self.request.user,
                device_id=device_id
            ).update(is_active=False)
        
        serializer.save(user=self.request.user)
    
    @extend_schema(
        summary='Activar/desactivar dispositivo',
        description='Alterna el estado activo/inactivo de un dispositivo.',
        tags=['notifications'],
        responses={200: OpenApiResponse(description='Estado del dispositivo actualizado')},
    )
    @action(detail=True, methods=['patch'])
    def toggle_active(self, request, pk=None):
        """Activar/desactivar dispositivo"""
        device = self.get_object()
        device.is_active = not device.is_active
        device.save()
        
        return Response({
            'message': f'Dispositivo {"activado" if device.is_active else "desactivado"}',
            'is_active': device.is_active
        })
    
    @extend_schema(
        summary='Enviar notificación de prueba',
        description='Envía una notificación de prueba al dispositivo seleccionado.',
        tags=['notifications'],
        responses={200: OpenApiResponse(description='Notificación de prueba enviada')},
    )
    @action(detail=True, methods=['post'])
    def test_notification(self, request, pk=None):
        """Enviar notificación de prueba a este dispositivo"""
        device = self.get_object()
        
        fcm_service = FCMService()
        success = fcm_service.send_notification(
            device.user,
            'Notificación de prueba',
            'Este es un mensaje de prueba desde la app',
            {'type': 'test', 'timestamp': timezone.now().isoformat()}
        )
        
        return Response({
            'message': 'Notificación de prueba enviada',
            'success': success
        })

@extend_schema_view(
    list=extend_schema(
        summary='Listar tipos de notificación',
        description='Obtiene la lista de tipos de notificaciones disponibles.',
        tags=['notifications'],
    ),
    retrieve=extend_schema(
        summary='Obtener tipo de notificación',
        description='Obtiene los detalles de un tipo de notificación específico.',
        tags=['notifications'],
    ),
)
class NotificationTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para tipos de notificaciones (solo lectura)
    """
    queryset = NotificationType.objects.filter(is_active=True)
    serializer_class = NotificationTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

@extend_schema(
    summary='Enviar notificación masiva',
    description='Envía una notificación a múltiples usuarios según roles o IDs específicos (solo administradores).',
    tags=['notifications'],
    request=BulkNotificationSerializer,
    responses={200: OpenApiResponse(description='Notificaciones enviadas')},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def send_bulk_notification(request):
    """
    Enviar notificación masiva a múltiples usuarios
    """
    serializer = BulkNotificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    title = serializer.validated_data['title']
    body = serializer.validated_data['body']
    user_roles = serializer.validated_data.get('user_roles', [])
    user_ids = serializer.validated_data.get('user_ids', [])
    data = serializer.validated_data.get('data', {})
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Construir query para usuarios objetivo
    users_query = User.objects.filter(status='active')
    
    if user_roles:
        users_query = users_query.filter(role__in=user_roles)
    
    if user_ids:
        users_query = users_query.filter(id__in=user_ids)
    
    users = users_query.all()
    
    if not users.exists():
        return Response(
            {'error': 'No se encontraron usuarios para enviar la notificación'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Enviar notificaciones de forma asíncrona
    success_count = 0
    for user in users:
        # Usar Celery para envío asíncrono
        send_push_notification.delay(
            user.id, title, body, data
        )
        success_count += 1
    
    return Response({
        'message': f'Notificaciones enviadas a {success_count} usuarios',
        'total_users': users.count(),
        'success_count': success_count
    })

@extend_schema(
    summary='Marcar notificación como leída (por ID)',
    description='Marca una notificación específica como leída usando su ID en la URL.',
    tags=['notifications'],
    parameters=[
        OpenApiParameter(name='notification_id', description='ID de la notificación', required=True, type=OpenApiTypes.INT, location=OpenApiParameter.PATH),
    ],
    responses={200: OpenApiResponse(description='Notificación marcada como leída')},
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_as_read(request, notification_id):
    """
    Marcar una notificación específica como leída
    """
    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )
        
        if notification.status != 'read':
            notification.status = 'read'
            notification.read_at = timezone.now()
            notification.save()
        
        return Response({
            'message': 'Notificación marcada como leída',
            'notification': NotificationSerializer(notification).data
        })
        
    except Notification.DoesNotExist:
        return Response(
            {'error': 'Notificación no encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )

@extend_schema(
    summary='Enviar notificación personalizada',
    description='Envía una notificación personalizada al usuario autenticado (para pruebas).',
    tags=['notifications'],
    responses={200: OpenApiResponse(description='Notificación enviada')},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_custom_notification(request):
    """
    Enviar notificación personalizada (para testing)
    """
    title = request.data.get('title', 'Notificación personalizada')
    body = request.data.get('body', 'Este es un mensaje personalizado')
    data = request.data.get('data', {})
    
    fcm_service = FCMService()
    success = fcm_service.send_notification(
        request.user, title, body, data
    )
    
    return Response({
        'message': 'Notificación enviada',
        'success': success,
        'title': title,
        'body': body
    })

@extend_schema(
    summary='Estadísticas de notificaciones',
    description='Obtiene estadísticas detalladas de las notificaciones del usuario autenticado.',
    tags=['notifications'],
    responses={200: OpenApiResponse(description='Estadísticas de notificaciones')},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_stats(request):
    """
    Obtener estadísticas de notificaciones del usuario
    """
    user_notifications = Notification.objects.filter(user=request.user)
    
    stats = {
        'total': user_notifications.count(),
        'unread': user_notifications.filter(
            status__in=['pending', 'sent', 'delivered']
        ).count(),
        'read': user_notifications.filter(status='read').count(),
        'failed': user_notifications.filter(status='failed').count(),
        'today': user_notifications.filter(
            created_at__date=timezone.now().date()
        ).count(),
        'this_week': user_notifications.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count()
    }
    
    # Notificaciones por tipo
    notification_types = user_notifications.values(
        'notification_type__name'
    ).annotate(
        count=models.Count('id')
    ).order_by('-count')[:5]
    
    stats['by_type'] = list(notification_types)
    
    return Response(stats)

@extend_schema(
    summary='Eliminar todas las notificaciones',
    description='Elimina todas las notificaciones del usuario autenticado.',
    tags=['notifications'],
    responses={200: OpenApiResponse(description='Notificaciones eliminadas')},
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_all_notifications(request):
    """
    Eliminar todas las notificaciones del usuario
    """
    deleted_count, _ = Notification.objects.filter(
        user=request.user
    ).delete()
    
    return Response({
        'message': f'{deleted_count} notificaciones eliminadas'
    })

@extend_schema(
    summary='Registrar token FCM',
    description='Registra el token FCM de un dispositivo para recibir notificaciones push.',
    tags=['notifications'],
    responses={200: OpenApiResponse(description='Token registrado correctamente')},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_device_token(request):
    """
    Registrar token FCM de dispositivo (shortcut para UserDeviceViewSet)
    """
    fcm_token = request.data.get('fcm_token')
    platform = request.data.get('platform')
    device_id = request.data.get('device_id')
    app_version = request.data.get('app_version')
    
    if not fcm_token or not platform:
        return Response(
            {'error': 'Se requieren fcm_token y platform'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Desactivar dispositivos anteriores del mismo usuario con el mismo token
    UserDevice.objects.filter(
        user=request.user,
        fcm_token=fcm_token
    ).update(is_active=False)
    
    # Crear nuevo dispositivo
    device = UserDevice.objects.create(
        user=request.user,
        fcm_token=fcm_token,
        platform=platform,
        device_id=device_id or '',
        app_version=app_version or '',
        is_active=True
    )
    
    return Response({
        'message': 'Token registrado correctamente',
        'device': UserDeviceSerializer(device).data
    })