from rest_framework import serializers
from .models import Driver, Trip, TripRating
from users.serializers import UserSerializer
from customers.serializers import CustomerSerializer
from core.utils.location import calculate_distance
from core.utils.payments import TripPricingService
from decimal import Decimal

class DriverSerializer(serializers.ModelSerializer):
    """Serializer completo para conductores"""
    user_info = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = Driver
        fields = [
            'id', 'user_info', 'license_number', 'vehicle_type',
            'vehicle_brand', 'vehicle_model', 'vehicle_year',
            'vehicle_plate', 'vehicle_color', 'status', 'availability',
            'current_latitude', 'current_longitude', 'rating',
            'total_trips', 'total_earnings', 'created_at'
        ]
        read_only_fields = [
            'user_info', 'status', 'rating', 'total_trips',
            'total_earnings', 'created_at'
        ]

class DriverRegistrationSerializer(serializers.ModelSerializer):
    """Serializer para registro de conductores"""
    
    class Meta:
        model = Driver
        fields = [
            'license_number', 'vehicle_type', 'vehicle_brand',
            'vehicle_model', 'vehicle_year', 'vehicle_plate',
            'vehicle_color'
        ]

class DriverLocationUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar ubicación"""
    
    class Meta:
        model = Driver
        fields = ['current_latitude', 'current_longitude']
        
    def update(self, instance, validated_data):
        from django.utils import timezone
        validated_data['last_location_update'] = timezone.now()
        return super().update(instance, validated_data)

class DriverAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer para cambiar disponibilidad"""
    
    class Meta:
        model = Driver
        fields = ['availability']

class DriverPublicSerializer(serializers.ModelSerializer):
    """Serializer público para conductores (para clientes)"""
    driver_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Driver
        fields = [
            'id', 'driver_name', 'vehicle_type', 'vehicle_brand',
            'vehicle_model', 'vehicle_color', 'rating', 'total_trips'
        ]

class TripSerializer(serializers.ModelSerializer):
    """Serializer completo para viajes"""
    customer_info = serializers.SerializerMethodField()
    driver_info = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Trip
        fields = [
            'id', 'trip_number', 'status', 'status_display', 'payment_status',
            'customer_info', 'driver_info', 'pickup_address', 'pickup_latitude',
            'pickup_longitude', 'destination_address', 'destination_latitude',
            'destination_longitude', 'estimated_distance', 'estimated_duration',
            'actual_distance', 'actual_duration', 'base_fare', 'distance_fare',
            'time_fare', 'surge_multiplier', 'total_fare', 'customer_notes',
            'created_at', 'accepted_at', 'started_at', 'completed_at', 'cancelled_at'
        ]
        read_only_fields = [
            'id', 'trip_number', 'customer_info', 'driver_info',
            'status_display', 'accepted_at', 'started_at', 'completed_at',
            'cancelled_at', 'created_at'
        ]
    
    def get_customer_info(self, obj):
        if obj.customer:
            return {
                'id': obj.customer.id,
                'name': obj.customer.user.get_full_name(),
                'phone': obj.customer.user.phone_number,
            }
        return None
    
    def get_driver_info(self, obj):
        if obj.driver:
            return {
                'id': obj.driver.id,
                'name': obj.driver.user.get_full_name(),
                'phone': obj.driver.user.phone_number,
                'vehicle': f"{obj.driver.vehicle_color} {obj.driver.vehicle_brand} {obj.driver.vehicle_model}",
                'plate': obj.driver.vehicle_plate,
                'rating': obj.driver.rating
            }
        return None

class TripCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear viajes"""
    
    class Meta:
        model = Trip
        fields = [
            'id', 'status', 'total_fare',
            'pickup_address', 'pickup_latitude', 'pickup_longitude',
            'destination_address', 'destination_latitude', 'destination_longitude',
            'customer_notes'
        ]
        read_only_fields = ['id', 'status', 'total_fare']
    
    def validate(self, attrs):
        # Validar que las coordenadas sean válidas
        pickup_lat = attrs.get('pickup_latitude')
        pickup_lon = attrs.get('pickup_longitude')
        dest_lat = attrs.get('destination_latitude')
        dest_lon = attrs.get('destination_longitude')
        
        if not all([pickup_lat, pickup_lon, dest_lat, dest_lon]):
            raise serializers.ValidationError("Se requieren todas las coordenadas")
            
        return attrs
    
    def create(self, validated_data):
        # Calcular distancia y duración estimada
        distance = calculate_distance(
            validated_data['pickup_latitude'],
            validated_data['pickup_longitude'],
            validated_data['destination_latitude'],
            validated_data['destination_longitude']
        )
        
        # Estimar duración (30 km/h promedio en ciudad)
        estimated_duration = (distance / 30) * 60  # minutos
        
        # Calcular precio
        pricing = TripPricingService.calculate_trip_price(distance, estimated_duration)
        
        # Crear viaje
        trip = Trip.objects.create(
            estimated_distance=Decimal(str(round(distance, 2))),
            estimated_duration=int(estimated_duration),
            base_fare=pricing['base_fare'],
            distance_fare=pricing['distance_fare'],
            time_fare=pricing['time_fare'],
            surge_multiplier=pricing['surge_multiplier'],
            total_fare=pricing['total'],
            **validated_data
        )
        
        return trip

class TripRatingSerializer(serializers.ModelSerializer):
    """Serializer para calificaciones de viajes"""
    trip_info = serializers.SerializerMethodField()
    
    class Meta:
        model = TripRating
        fields = [
            'id', 'trip_info', 'rating_type', 'rating',
            'comment', 'created_at'
        ]
        read_only_fields = ['id', 'trip_info', 'created_at']
    
    def get_trip_info(self, obj):
        return {
            'trip_number': obj.trip.trip_number,
            'pickup_address': obj.trip.pickup_address,
            'destination_address': obj.trip.destination_address,
            'total_fare': obj.trip.total_fare
        }

class TripRatingCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear calificaciones"""
    
    class Meta:
        model = TripRating
        fields = ['trip', 'rating_type', 'rating', 'comment']
    
    def validate(self, attrs):
        request = self.context['request']
        trip = attrs['trip']
        rating_type = attrs['rating_type']
        
        # Verificar que el viaje esté completado
        if trip.status != 'completed':
            raise serializers.ValidationError("Solo puedes calificar viajes completados")
        
        # Verificar permisos según el tipo de calificación
        if rating_type == 'customer_to_driver':
            if trip.customer.user != request.user:
                raise serializers.ValidationError("No puedes calificar este viaje")
        elif rating_type == 'driver_to_customer':
            if not hasattr(request.user, 'driver_profile') or trip.driver != request.user.driver_profile:
                raise serializers.ValidationError("No puedes calificar este viaje")
        
        # Verificar que no se haya calificado antes
        if TripRating.objects.filter(trip=trip, rating_type=rating_type).exists():
            raise serializers.ValidationError("Ya has calificado este viaje")
        
        return attrs

class TripEstimateSerializer(serializers.Serializer):
    """Serializer para estimaciones de viaje"""
    pickup_latitude = serializers.DecimalField(max_digits=10, decimal_places=8)
    pickup_longitude = serializers.DecimalField(max_digits=11, decimal_places=8)
    destination_latitude = serializers.DecimalField(max_digits=10, decimal_places=8)
    destination_longitude = serializers.DecimalField(max_digits=11, decimal_places=8)
    vehicle_type = serializers.ChoiceField(
        choices=Driver.VEHICLE_CHOICES,
        required=False,
        default='car'
    )