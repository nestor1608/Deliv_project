from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Avg
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import Driver, Trip, TripRating
from .serializers import (
    DriverSerializer, DriverRegistrationSerializer, DriverLocationUpdateSerializer,
    DriverAvailabilitySerializer, TripSerializer, TripCreateSerializer,
    TripRatingSerializer, TripRatingCreateSerializer, TripEstimateSerializer
)
from customers.permissions import IsCustomer
from core.utils.location import calculate_distance
from core.utils.driver_assignment import DriverAssignmentService
from core.utils.payments import TripPricingService

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from core.throttles import LocationRateThrottle

@extend_schema_view(
    list=extend_schema(
        summary='Listar conductores',
        description='Obtiene la lista de conductores. Los conductores ven su propio perfil, los administradores ven todos, los clientes ven conductores aprobados.',
        tags=['mobility'],
    ),
    create=extend_schema(
        summary='Crear conductor',
        description='Registra un nuevo conductor en el sistema.',
        tags=['mobility'],
    ),
    retrieve=extend_schema(
        summary='Obtener conductor',
        description='Obtiene los detalles de un conductor específico.',
        tags=['mobility'],
    ),
    update=extend_schema(
        summary='Actualizar conductor',
        description='Actualiza los datos completos de un conductor.',
        tags=['mobility'],
    ),
    partial_update=extend_schema(
        summary='Actualizar parcialmente conductor',
        description='Actualiza parcialmente los datos de un conductor.',
        tags=['mobility'],
    ),
)
class DriverViewSet(viewsets.ModelViewSet):
    """
    ViewSet para conductores
    """
    serializer_class = DriverSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'availability', 'vehicle_type']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'vehicle_brand', 'vehicle_model']
    ordering_fields = ['rating', 'total_trips', 'created_at']
    ordering = ['-rating']
    
    def get_queryset(self):
        if hasattr(self.request.user, 'driver_profile'):
            # Si es conductor, solo ve su propio perfil
            return Driver.objects.filter(user=self.request.user)
        elif self.request.user.role == 'admin':
            # Admin ve todos
            return Driver.objects.all()
        else:
            # Clientes ven conductores aprobados y disponibles
            return Driver.objects.filter(status='approved')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DriverRegistrationSerializer
        return DriverSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        elif self.action == 'create':
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @extend_schema(
        summary='Actualizar ubicación',
        description='Actualiza la ubicación geográfica del conductor.',
        tags=['mobility'],
        request=DriverLocationUpdateSerializer,
        responses={200: OpenApiResponse(description='Ubicación actualizada correctamente')},
    )
    @action(detail=True, methods=['patch'], throttle_classes=[LocationRateThrottle])
    def update_location(self, request, pk=None):
        """Actualizar ubicación del conductor"""
        driver = self.get_object()
        
        # Verificar que el usuario es dueño del perfil
        if driver.user != request.user:
            return Response(
                {'error': 'No tienes permisos para actualizar esta ubicación'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DriverLocationUpdateSerializer(
            driver, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({'message': 'Ubicación actualizada correctamente'})
    
    @extend_schema(
        summary='Cambiar disponibilidad',
        description='Cambia la disponibilidad actual del conductor.',
        tags=['mobility'],
        request=DriverAvailabilitySerializer,
        responses={200: OpenApiResponse(description='Disponibilidad actualizada')},
    )
    @action(detail=True, methods=['patch'])
    def update_availability(self, request, pk=None):
        """Cambiar disponibilidad del conductor"""
        driver = self.get_object()
        
        if driver.user != request.user:
            return Response(
                {'error': 'No tienes permisos para cambiar esta disponibilidad'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        new_availability = request.data.get('availability')
        
        # Block going online if KYC not approved
        if new_availability == 'available' and driver.background_check_status != 'approved':
            return Response(
                {'error': 'Debes completar la verificación KYC antes de estar disponible'},
                status=400
            )
        
        serializer = DriverAvailabilitySerializer(
            driver, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Disponibilidad actualizada',
            'availability': driver.availability
        })
    
    @extend_schema(
        summary='Viajes activos',
        description='Obtiene los viajes activos asignados al conductor.',
        tags=['mobility'],
        responses={200: TripSerializer(many=True)},
    )
    @action(detail=True, methods=['get'])
    def active_trips(self, request, pk=None):
        """Obtener viajes activos del conductor"""
        driver = self.get_object()
        
        if driver.user != request.user:
            return Response(
                {'error': 'No tienes permisos'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        trips = Trip.objects.filter(
            driver=driver,
            status__in=['accepted', 'driver_arrived', 'in_progress']
        ).order_by('-created_at')
        
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary='Ganancias del conductor',
        description='Obtiene las ganancias totales del conductor con filtros opcionales por fecha.',
        tags=['mobility'],
        parameters=[
            OpenApiParameter(name='from_date', description='Fecha inicial (YYYY-MM-DD)', required=False, type=OpenApiTypes.DATE),
            OpenApiParameter(name='to_date', description='Fecha final (YYYY-MM-DD)', required=False, type=OpenApiTypes.DATE),
        ],
        responses={200: OpenApiResponse(description='Ganancias del conductor')},
    )
    @action(detail=True, methods=['get'])
    def earnings(self, request, pk=None):
        """Obtener ganancias del conductor"""
        driver = self.get_object()
        
        if driver.user != request.user:
            return Response(
                {'error': 'No tienes permisos'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Filtros de fecha opcionales
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        trips = Trip.objects.filter(
            driver=driver,
            status='completed'
        )
        
        if from_date:
            trips = trips.filter(completed_at__gte=from_date)
        if to_date:
            trips = trips.filter(completed_at__lte=to_date)
        
        total_earnings = sum(trip.total_fare for trip in trips)
        total_trips = trips.count()
        
        return Response({
            'total_earnings': total_earnings,
            'total_trips': total_trips,
            'average_per_trip': total_earnings / total_trips if total_trips else 0,
            'driver_rating': driver.rating
        })
    
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_kyc(self, request, pk=None):
        driver = self.get_object()
        if driver.user != request.user:
            return Response({'error': 'No puedes modificar este perfil'}, status=403)
        for field in ['id_document_front', 'id_document_back', 'selfie']:
            if field in request.FILES:
                setattr(driver, field, request.FILES[field])
        driver.background_check_status = 'pending'
        driver.kyc_submitted_at = timezone.now()
        driver.save()
        return Response({'message': 'Documentos subidos', 'status': driver.background_check_status})
    
    @action(detail=True, methods=['post'])
    def approve_kyc(self, request, pk=None):
        if request.user.role != 'admin':
            return Response({'error': 'Solo administradores'}, status=403)
        driver = self.get_object()
        driver.background_check_status = 'approved'
        driver.kyc_verified_at = timezone.now()
        driver.status = 'approved'
        driver.save()
        return Response({'message': 'KYC aprobado', 'status': 'approved'})
    
    @action(detail=True, methods=['post'])
    def reject_kyc(self, request, pk=None):
        if request.user.role != 'admin':
            return Response({'error': 'Solo administradores'}, status=403)
        driver = self.get_object()
        driver.background_check_status = 'rejected'
        driver.kyc_verified_at = None
        driver.save()
        return Response({'message': 'KYC rechazado', 'status': 'rejected'})

@extend_schema_view(
    list=extend_schema(
        summary='Listar viajes',
        description='Obtiene la lista de viajes según el perfil del usuario (cliente, conductor o admin).',
        tags=['mobility'],
    ),
    create=extend_schema(
        summary='Crear viaje',
        description='Crea una nueva solicitud de viaje.',
        tags=['mobility'],
    ),
    retrieve=extend_schema(
        summary='Obtener viaje',
        description='Obtiene los detalles de un viaje específico.',
        tags=['mobility'],
    ),
    update=extend_schema(
        summary='Actualizar viaje',
        description='Actualiza los datos completos de un viaje.',
        tags=['mobility'],
    ),
    partial_update=extend_schema(
        summary='Actualizar parcialmente viaje',
        description='Actualiza parcialmente los datos de un viaje.',
        tags=['mobility'],
    ),
)
class TripViewSet(viewsets.ModelViewSet):
    """
    ViewSet para viajes
    """
    serializer_class = TripSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_status']
    search_fields = ['trip_number', 'pickup_address', 'destination_address']
    ordering_fields = ['created_at', 'total_fare']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'customer' and hasattr(user, 'customer_profile'):
            return Trip.objects.filter(customer=user.customer_profile)
        elif hasattr(user, 'driver_profile'):
            return Trip.objects.filter(driver=user.driver_profile)
        elif user.role == 'admin':
            return Trip.objects.all()
        else:
            return Trip.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TripCreateSerializer
        return TripSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated, IsCustomer]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        serializer.save(customer=self.request.user.customer_profile)
    
    @extend_schema(
        summary='Aceptar viaje',
        description='Permite a un conductor aceptar un viaje solicitado.',
        tags=['mobility'],
        responses={200: TripSerializer()},
    )
    @action(detail=True, methods=['patch'])
    def accept_trip(self, request, pk=None):
        """Conductor acepta el viaje"""
        trip = self.get_object()
        
        if not hasattr(request.user, 'driver_profile'):
            return Response(
                {'error': 'Solo conductores pueden aceptar viajes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        driver = request.user.driver_profile
        
        if trip.status != 'requested':
            return Response(
                {'error': 'Este viaje ya no está disponible'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if driver.availability != 'available':
            return Response(
                {'error': 'No estás disponible para aceptar viajes'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Asignar conductor y cambiar estado
        trip.driver = driver
        trip.status = 'accepted'
        trip.accepted_at = timezone.now()
        trip.save()
        
        # Cambiar disponibilidad del conductor
        driver.availability = 'busy'
        driver.save()
        
        return Response({
            'message': 'Viaje aceptado correctamente',
            'trip': TripSerializer(trip).data
        })
    
    @extend_schema(
        summary='Iniciar viaje',
        description='Marca el viaje como en progreso cuando el conductor ha llegado al punto de recogida.',
        tags=['mobility'],
        responses={200: TripSerializer()},
    )
    @action(detail=True, methods=['patch'])
    def start_trip(self, request, pk=None):
        """Iniciar el viaje (conductor llegó al punto de recogida)"""
        trip = self.get_object()
        
        if trip.driver.user != request.user:
            return Response(
                {'error': 'No eres el conductor asignado'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if trip.status not in ['accepted', 'driver_arrived']:
            return Response(
                {'error': 'No puedes iniciar este viaje'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        trip.status = 'in_progress'
        trip.started_at = timezone.now()
        trip.save()
        
        return Response({
            'message': 'Viaje iniciado',
            'trip': TripSerializer(trip).data
        })
    
    @extend_schema(
        summary='Completar viaje',
        description='Marca el viaje como completado y libera al conductor.',
        tags=['mobility'],
        responses={200: TripSerializer()},
    )
    @action(detail=True, methods=['patch'])
    def complete_trip(self, request, pk=None):
        """Completar el viaje"""
        trip = self.get_object()
        
        if trip.driver.user != request.user:
            return Response(
                {'error': 'No eres el conductor asignado'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if trip.status != 'in_progress':
            return Response(
                {'error': 'El viaje debe estar en progreso'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Datos opcionales del viaje completado
        actual_distance = request.data.get('actual_distance')
        actual_duration = request.data.get('actual_duration')
        
        if actual_distance:
            trip.actual_distance = actual_distance
        if actual_duration:
            trip.actual_duration = actual_duration
        
        trip.status = 'completed'
        trip.completed_at = timezone.now()
        trip.save()
        
        # Liberar conductor
        trip.driver.availability = 'available'
        trip.driver.total_trips += 1
        trip.driver.total_earnings += trip.total_fare
        trip.driver.save()
        
        return Response({
            'message': 'Viaje completado',
            'trip': TripSerializer(trip).data
        })
    
    @extend_schema(
        summary='Cancelar viaje',
        description='Cancela un viaje existente. Puede ser ejecutado por el cliente o el conductor.',
        tags=['mobility'],
        responses={200: TripSerializer()},
    )
    @action(detail=True, methods=['patch'])
    def cancel_trip(self, request, pk=None):
        """Cancelar viaje"""
        trip = self.get_object()
        reason = request.data.get('reason', '')
        
        # Verificar permisos
        if trip.customer.user != request.user and (trip.driver and trip.driver.user != request.user):
            return Response(
                {'error': 'No tienes permisos para cancelar este viaje'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if trip.status in ['completed', 'cancelled_customer', 'cancelled_driver']:
            return Response(
                {'error': 'No se puede cancelar este viaje'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determinar quién cancela
        if trip.customer.user == request.user:
            trip.status = 'cancelled_customer'
        else:
            trip.status = 'cancelled_driver'
        
        trip.cancelled_at = timezone.now()
        trip.cancellation_reason = reason
        trip.save()
        
        # Liberar conductor si estaba asignado
        if trip.driver:
            trip.driver.availability = 'available'
            trip.driver.save()
        
        return Response({
            'message': 'Viaje cancelado',
            'trip': TripSerializer(trip).data
        })

@extend_schema_view(
    list=extend_schema(
        summary='Listar calificaciones',
        description='Obtiene la lista de calificaciones de viajes según el perfil del usuario.',
        tags=['mobility'],
    ),
    create=extend_schema(
        summary='Crear calificación',
        description='Crea una nueva calificación para un viaje completado.',
        tags=['mobility'],
        request=TripRatingCreateSerializer,
        responses={201: TripRatingSerializer()},
    ),
)
class TripRatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet para calificaciones de viajes
    """
    serializer_class = TripRatingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'customer' and hasattr(user, 'customer_profile'):
            return TripRating.objects.filter(
                trip__customer=user.customer_profile,
                rating_type='customer_to_driver'
            )
        elif hasattr(user, 'driver_profile'):
            return TripRating.objects.filter(
                trip__driver=user.driver_profile,
                rating_type='driver_to_customer'
            )
        else:
            return TripRating.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TripRatingCreateSerializer
        return TripRatingSerializer


@extend_schema(
    summary='Estimar viaje',
    description='Calcula una estimación de precio, distancia y duración para un viaje.',
    tags=['mobility'],
    request=TripEstimateSerializer,
    responses={200: OpenApiResponse(description='Estimación del viaje')},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCustomer])
def trip_estimate(request):
    """
    Calcular estimación de precio y tiempo para un viaje
    """
    pickup_lat = request.data.get('pickup_latitude')
    pickup_lon = request.data.get('pickup_longitude')
    dest_lat = request.data.get('destination_latitude')
    dest_lon = request.data.get('destination_longitude')
    
    if not all([pickup_lat, pickup_lon, dest_lat, dest_lon]):
        return Response(
            {'error': 'Se requieren coordenadas de origen y destino'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Calcular distancia
        distance = calculate_distance(pickup_lat, pickup_lon, dest_lat, dest_lon)
        
        # Estimar duración (velocidad promedio 30 km/h en ciudad)
        estimated_duration = (distance / 30) * 60  # minutos
        
        # Calcular precio
        pricing = TripPricingService.calculate_trip_price(
            distance, estimated_duration
        )
        
        return Response({
            'estimated_distance': round(distance, 2),
            'estimated_duration': round(estimated_duration),
            'pricing': pricing,
            'available_drivers': Driver.objects.filter(
                status='approved',
                availability='available'
            ).count()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Error calculando estimación: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@extend_schema(
    summary='Conductores cercanos',
    description='Obtiene una lista de conductores disponibles cercanos a una ubicación geográfica.',
    tags=['mobility'],
    parameters=[
        OpenApiParameter(name='latitude', description='Latitud de la ubicación', required=True, type=OpenApiTypes.FLOAT),
        OpenApiParameter(name='longitude', description='Longitud de la ubicación', required=True, type=OpenApiTypes.FLOAT),
        OpenApiParameter(name='radius', description='Radio de búsqueda en kilómetros (default: 10)', required=False, type=OpenApiTypes.FLOAT),
    ],
    responses={200: OpenApiResponse(description='Lista de conductores cercanos')},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def nearby_drivers(request):
    """
    Obtener conductores cercanos a una ubicación
    """
    lat = request.query_params.get('latitude')
    lon = request.query_params.get('longitude')
    radius = float(request.query_params.get('radius', 10))  # km
    
    if not lat or not lon:
        return Response(
            {'error': 'Se requieren parámetros latitude y longitude'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        available_drivers = Driver.objects.filter(
            status='approved',
            availability='available',
            current_latitude__isnull=False,
            current_longitude__isnull=False
        )
        
        nearby_drivers = []
        
        for driver in available_drivers:
            distance = calculate_distance(
                lat, lon,
                driver.current_latitude,
                driver.current_longitude
            )
            
            if distance <= radius:
                nearby_drivers.append({
                    'driver': DriverSerializer(driver).data,
                    'distance': round(distance, 2)
                })
        
        # Ordenar por distancia
        nearby_drivers.sort(key=lambda x: x['distance'])
        
        return Response({
            'drivers': nearby_drivers,
            'total_count': len(nearby_drivers)
        })
        
    except Exception as e:
        return Response(
            {'error': f'Error buscando conductores: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )