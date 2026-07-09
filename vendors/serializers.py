from rest_framework import serializers
from .models import VendorCategory, Vendor, Product, VendorRating
from users.serializers import UserSerializer

class VendorCategorySerializer(serializers.ModelSerializer):
    """Serializer para categorías de comercios"""
    
    class Meta:
        model = VendorCategory
        fields = ['id', 'name', 'description', 'icon', 'is_active']

class VendorListSerializer(serializers.ModelSerializer):
    """Serializer para listado de comercios (vista resumida)"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    distance = serializers.FloatField(read_only=True, required=False)
    
    class Meta:
        model = Vendor
        fields = [
            'id', 'business_name', 'category_name', 'rating',
            'delivery_fee', 'delivery_time', 'is_open',
            'minimum_order', 'distance'
        ]

class VendorSerializer(serializers.ModelSerializer):
    """Serializer completo para comercios"""
    user_info = UserSerializer(source='user', read_only=True)
    category_info = VendorCategorySerializer(source='category', read_only=True)
    
    class Meta:
        model = Vendor
        fields = [
            'id', 'user_info', 'business_name', 'category_info',
            'description', 'address', 'latitude', 'longitude',
            'delivery_fee', 'minimum_order', 'delivery_time',
            'delivery_radius', 'rating', 'total_orders',
            'is_open', 'opening_time', 'closing_time', 'status'
        ]
        read_only_fields = ['user_info', 'rating', 'total_orders', 'status']

class VendorRegistrationSerializer(serializers.ModelSerializer):
    """Serializer para registro de nuevos comercios"""
    
    class Meta:
        model = Vendor
        fields = [
            'business_name', 'category', 'description',
            'business_license', 'tax_id', 'address',
            'latitude', 'longitude', 'delivery_fee',
            'minimum_order', 'delivery_time', 'delivery_radius',
            'opening_time', 'closing_time'
        ]

class ProductSerializer(serializers.ModelSerializer):
    """Serializer para productos"""
    vendor_name = serializers.CharField(source='vendor.business_name', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'vendor_name', 'name', 'description', 'price',
            'image', 'category', 'stock', 'is_available',
            'times_ordered', 'created_at'
        ]
        read_only_fields = ['vendor_name', 'times_ordered', 'created_at']

class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para crear/actualizar productos"""
    
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'price', 'image',
            'category', 'stock', 'is_available'
        ]

class VendorRatingSerializer(serializers.ModelSerializer):
    """Serializer para calificaciones de comercios"""
    customer_name = serializers.CharField(source='customer.user.get_full_name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    
    class Meta:
        model = VendorRating
        fields = [
            'id', 'customer_name', 'order_number', 'rating',
            'comment', 'created_at'
        ]
        read_only_fields = ['customer_name', 'order_number', 'created_at']

class VendorRatingCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear calificaciones"""
    
    class Meta:
        model = VendorRating
        fields = ['vendor', 'order', 'rating', 'comment']
    
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
        if VendorRating.objects.filter(customer=customer, order=order).exists():
            raise serializers.ValidationError("Ya has calificado este pedido")
        
        return attrs
    
    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user.customer_profile
        return super().create(validated_data)