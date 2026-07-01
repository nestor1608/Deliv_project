from decimal import Decimal
from rest_framework import serializers
from .models import Order, OrderItem, Product, OrderStatusHistory


class ProductSerializer(serializers.ModelSerializer):
    """Serializer para productos"""
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'image',
            'is_available', 'category'
        ]

class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer para items del pedido"""
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'product_id', 'quantity',
            'unit_price', 'total_price', 'special_instructions'
        ]
        read_only_fields = ['id', 'unit_price', 'total_price']

class OrderStatusHistorySerializer(serializers.ModelSerializer):
    """Serializer para historial de estados"""
    changed_by_name = serializers.CharField(source='changed_by.get_full_name', read_only=True)
    
    class Meta:
        model = OrderStatusHistory
        fields = [
            'id', 'previous_status', 'new_status', 'changed_by_name',
            'notes', 'timestamp'
        ]

class OrderSerializer(serializers.ModelSerializer):
    """Serializer completo para pedidos"""
    items = OrderItemSerializer(many=True, read_only=True)
    customer_info = serializers.SerializerMethodField()
    vendor_info = serializers.SerializerMethodField()
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'payment_status',
            'customer_info', 'vendor_info', 'delivery_address',
            'subtotal', 'delivery_fee', 'tax_amount', 'total_amount',
            'estimated_delivery_time', 'customer_notes', 'vendor_notes',
            'items', 'status_history', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order_number', 'created_at', 'updated_at'
        ]
    
    def get_customer_info(self, obj):
        return {
            'id': obj.customer.id,
            'name': obj.customer.user.get_full_name(),
            'phone': obj.customer.user.phone_number,
        }
    
    def get_vendor_info(self, obj):
        return {
            'id': obj.vendor.id,
            'business_name': obj.vendor.business_name,
        }

class CreateOrderSerializer(serializers.ModelSerializer):
    """Serializer para crear nuevos pedidos"""
    items = OrderItemSerializer(many=True)
    
    class Meta:
        model = Order
        fields = [
            'vendor', 'delivery_address', 'delivery_latitude',
            'delivery_longitude', 'customer_notes', 'items'
        ]
    
    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("El pedido debe incluir al menos un producto")
        return value
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # Crear el pedido con valores iniciales para campos no nulos
        order = Order.objects.create(
            customer=self.context['request'].user.customer_profile,
            subtotal=Decimal('0.00'),
            total_amount=Decimal('0.00'),
            **validated_data
        )
        
        # Crear los items y calcular totales
        subtotal = Decimal('0.00')
        for item_data in items_data:
            try:
                product = Product.objects.get(id=item_data['product_id'])
            except Product.DoesNotExist:
                raise serializers.ValidationError(
                    {'items': f"Producto con id {item_data['product_id']} no existe"}
                )
            item_data['product'] = product
            item_data['unit_price'] = product.price
            
            order_item = OrderItem.objects.create(order=order, **item_data)
            subtotal += order_item.total_price
        
        # Calcular totales del pedido
        delivery_fee = Decimal('150.00')  # Fee fijo por ahora
        tax_amount = subtotal * Decimal('0.21')  # IVA 21%
        
        order.subtotal = subtotal
        order.delivery_fee = delivery_fee
        order.tax_amount = tax_amount
        order.total_amount = subtotal + delivery_fee + tax_amount
        order.save()
        
        return order