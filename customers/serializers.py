from rest_framework import serializers
from .models import Customer, CustomerAddress
from users.serializers import UserSerializer

class CustomerSerializer(serializers.ModelSerializer):
    """Serializer para perfil de cliente"""
    user_info = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = Customer
        fields = [
            'id', 'user_info', 'date_of_birth', 'loyalty_points',
            'preferred_payment_method', 'is_premium', 'created_at'
        ]
        read_only_fields = ['id', 'loyalty_points', 'created_at']

class CustomerAddressSerializer(serializers.ModelSerializer):
    """Serializer para direcciones del cliente"""
    
    class Meta:
        model = CustomerAddress
        fields = [
            'id', 'label', 'street_address', 'city', 'state',
            'postal_code', 'country', 'latitude', 'longitude',
            'is_default', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate(self, attrs):
        # Si se marca como default, asegurar que sea única
        if attrs.get('is_default'):
            customer = self.context['request'].user.customer_profile
            if self.instance:
                # Al actualizar, excluir la instancia actual
                CustomerAddress.objects.filter(
                    customer=customer, is_default=True
                ).exclude(id=self.instance.id).update(is_default=False)
            else:
                # Al crear, quitar default de todas las demás
                CustomerAddress.objects.filter(
                    customer=customer, is_default=True
                ).update(is_default=False)
        
        return attrs