from rest_framework import serializers
from .models import DeliveryPerson, DeliveryRating
from users.serializers import UserSerializer
from orders.models import Order

class DeliveryPersonSerializer(serializers.ModelSerializer):
    """Serializer para repartidores"""
    user_info = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = DeliveryPerson
        fields = [
            'id', 'user_info', 'license_number', 'vehicle_type',
            'vehicle_plate', 'status', 'availability',
            'current_latitude', 'current_longitude',
            'rating', 'total_deliveries', 'total_earnings',
            'created_at'
        ]
        read_only_fields = [
            'user_info', 'rating', 'total_deliveries', 
            'total_earnings', 'status', 'created_at'
        ]

class DeliveryPersonRegistrationSerializer(serializers.ModelSerializer):
    """Serializer para registro de repartidores"""
    
    class Meta:
        model = DeliveryPerson
        fields = [
            'license_number', 'vehicle_type', 'vehicle_plate'
        ]

class DeliveryLocationUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar ubicación"""
    
    class Meta:
        model = DeliveryPerson
        fields = ['current_latitude', 'current_longitude']
        
    def update(self, instance, validated_data):
        from django.utils import timezone
        validated_data['last_location_update'] = timezone.now()
        return super().update(instance, validated_data)

class DeliveryAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer para cambiar disponibilidad"""
    
    class Meta:
        model = DeliveryPerson
        fields = ['availability']

class DeliveryRatingSerializer(serializers.ModelSerializer):
    """Serializer para calificaciones de repartidores"""
    customer_name = serializers.CharField(source='customer.user.get_full_name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    
    class Meta:
        model = DeliveryRating
        fields = [
            'id', 'customer_name', 'order_number', 'rating',
            'comment', 'created_at'
        ]
        read_only_fields = ['customer_name', 'order_number', 'created_at']

class DeliveryRatingCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear calificaciones de repartidores"""
    
    class Meta:
        model = DeliveryRating
        fields = ['delivery_person', 'order', 'rating', 'comment']
    
    def validate(self, attrs):
        request = self.context['request']
        customer = request.user.customer_profile
        order = attrs['order']
        
        # Verificar que el pedido pertenece al cliente
        if order.customer != customer:
            raise serializers.ValidationError("No puedes calificar un pedido que no es tuyo")
        
        # Verificar que el pedido esté entregado
        if order.status != 'delivered':
            raise serializers.ValidationError("Solo puedes calificar pedidos entregados")
        
        # Verificar que no se haya calificado antes
        if DeliveryRating.objects.filter(customer=customer, order=order).exists():
            raise serializers.ValidationError("Ya has calificado este pedido")
        
        return attrs
    
    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user.customer_profile
        return super().create(validated_data)

# Importar OrderSerializer para evitar importación circular
class OrderSerializer(serializers.ModelSerializer):
    """Serializer básico para pedidos (para repartidores)"""
    customer_name = serializers.CharField(source='customer.user.get_full_name', read_only=True)
    vendor_name = serializers.CharField(source='vendor.business_name', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'customer_name', 'vendor_name',
            'delivery_address', 'total_amount', 'delivery_fee',
            'estimated_delivery_time', 'created_at'
        ]
        read_only_fields = ['id', 'order_number', 'customer_name', 'vendor_name', 'created_at']