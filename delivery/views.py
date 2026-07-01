from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Avg
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import *
from .serializers import *
from customers.permissions import IsCustomer

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes


@extend_schema_view(
    list=extend_schema(
        summary='Listar repartidores',
        description='Obtiene la lista de repartidores según el perfil del usuario.',
        tags=['delivery'],
    ),
    create=extend_schema(
        summary='Crear repartidor',
        description='Registra un nuevo repartidor en el sistema.',
        tags=['delivery'],
    ),
    retrieve=extend_schema(
        summary='Obtener repartidor',
        description='Obtiene los detalles de un repartidor específico.',
        tags=['delivery'],
    ),
    update=extend_schema(
        summary='Actualizar repartidor',
        description='Actualiza los datos completos de un repartidor.',
        tags=['delivery'],
    ),
    partial_update=extend_schema(
        summary='Actualizar parcialmente repartidor',
        description='Actualiza parcialmente los datos de un repartidor.',
        tags=['delivery'],
    ),
)
class DeliveryPersonViewSet(viewsets.ModelViewSet):
    """
    ViewSet para repartidores
    """
    serializer_class = DeliveryPersonSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request.user, 'delivery_profile'):
            return DeliveryPerson.objects.filter(user=self.request.user)
        return DeliveryPerson.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DeliveryPersonRegistrationSerializer
        return DeliveryPersonSerializer
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @extend_schema(
        summary='Actualizar ubicación',
        description='Actualiza la ubicación geográfica del repartidor.',
        tags=['delivery'],
        request=DeliveryLocationUpdateSerializer,
        responses={200: OpenApiResponse(description='Ubicación actualizada correctamente')},
    )
    @action(detail=True, methods=['patch'])
    def update_location(self, request, pk=None):
        """
        Actualizar ubicación del repartidor
        """
        delivery_person = self.get_object()
        serializer = DeliveryLocationUpdateSerializer(
            delivery_person, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({'message': 'Ubicación actualizada correctamente'})
    
    @extend_schema(
        summary='Cambiar disponibilidad',
        description='Cambia la disponibilidad actual del repartidor.',
        tags=['delivery'],
        request=DeliveryAvailabilitySerializer,
        responses={200: OpenApiResponse(description='Disponibilidad actualizada')},
    )
    @action(detail=True, methods=['patch'])
    def update_availability(self, request, pk=None):
        """
        Cambiar disponibilidad del repartidor
        """
        delivery_person = self.get_object()
        serializer = DeliveryAvailabilitySerializer(
            delivery_person, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Disponibilidad actualizada',
            'availability': delivery_person.availability
        })
    
    @extend_schema(
        summary='Pedidos activos',
        description='Obtiene los pedidos activos asignados al repartidor.',
        tags=['delivery'],
        responses={200: OrderSerializer(many=True)},
    )
    @action(detail=True, methods=['get'])
    def active_orders(self, request, pk=None):
        """
        Obtener pedidos activos del repartidor
        """
        delivery_person = self.get_object()
        orders = Order.objects.filter(
            delivery_person=delivery_person,
            status__in=['picked_up', 'ready']
        ).order_by('-created_at')
        
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary='Ganancias del repartidor',
        description='Obtiene las ganancias totales del repartidor con filtros opcionales por fecha.',
        tags=['delivery'],
        parameters=[
            OpenApiParameter(name='from_date', description='Fecha inicial (YYYY-MM-DD)', required=False, type=OpenApiTypes.DATE),
            OpenApiParameter(name='to_date', description='Fecha final (YYYY-MM-DD)', required=False, type=OpenApiTypes.DATE),
        ],
        responses={200: OpenApiResponse(description='Ganancias del repartidor')},
    )
    @action(detail=True, methods=['get'])
    def earnings(self, request, pk=None):
        """
        Obtener ganancias del repartidor
        """
        delivery_person = self.get_object()
        
        # Filtros de fecha opcionales
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        orders = Order.objects.filter(
            delivery_person=delivery_person,
            status='delivered'
        )
        
        if from_date:
            orders = orders.filter(delivered_at__gte=from_date)
        if to_date:
            orders = orders.filter(delivered_at__lte=to_date)
        
        total_earnings = sum(order.delivery_fee for order in orders)
        total_deliveries = orders.count()
        
        return Response({
            'total_earnings': total_earnings,
            'total_deliveries': total_deliveries,
            'average_per_delivery': total_earnings / total_deliveries if total_deliveries else 0
        })

@extend_schema_view(
    list=extend_schema(
        summary='Listar calificaciones',
        description='Obtiene la lista de calificaciones de repartidores para el cliente autenticado.',
        tags=['delivery'],
    ),
    create=extend_schema(
        summary='Crear calificación',
        description='Crea una nueva calificación para un repartidor.',
        tags=['delivery'],
        request=DeliveryRatingCreateSerializer,
        responses={201: DeliveryRatingSerializer()},
    ),
)
class DeliveryRatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet para calificaciones de repartidores
    """
    serializer_class = DeliveryRatingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request.user, 'customer_profile'):
            return DeliveryRating.objects.filter(customer=self.request.user.customer_profile)
        return DeliveryRating.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DeliveryRatingCreateSerializer
        return DeliveryRatingSerializer
    
    def get_permissions(self):
        permission_classes = [IsAuthenticated, IsCustomer]
        return [permission() for permission in permission_classes]