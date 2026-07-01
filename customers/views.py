from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from .models import Customer, CustomerAddress
from .serializers import CustomerSerializer, CustomerAddressSerializer

@extend_schema_view(
    get=extend_schema(
        summary='Obtener perfil de cliente',
        description='Retorna los datos del perfil de cliente del usuario autenticado. Si no existe un perfil de cliente, lo crea automáticamente.',
        responses={200: CustomerSerializer},
        tags=['customers'],
    ),
    put=extend_schema(
        summary='Actualizar perfil de cliente (completo)',
        description='Actualiza todos los datos del perfil de cliente del usuario autenticado.',
        request=CustomerSerializer,
        responses={200: CustomerSerializer},
        tags=['customers'],
    ),
    patch=extend_schema(
        summary='Actualizar perfil de cliente (parcial)',
        description='Actualiza parcialmente los datos del perfil de cliente del usuario autenticado.',
        request=CustomerSerializer,
        responses={200: CustomerSerializer},
        tags=['customers'],
    ),
)
class CustomerProfileView(generics.RetrieveUpdateAPIView):
    """Vista para ver y actualizar perfil de cliente"""
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        customer, created = Customer.objects.get_or_create(
            user=self.request.user
        )
        return customer

@extend_schema_view(
    get=extend_schema(
        summary='Listar direcciones del cliente',
        description='Retorna la lista de direcciones guardadas del cliente autenticado.',
        responses={200: CustomerAddressSerializer(many=True)},
        tags=['customers'],
    ),
    post=extend_schema(
        summary='Crear dirección del cliente',
        description='Crea una nueva dirección para el cliente autenticado. Si se marca como predeterminada, las demás direcciones se desmarcan automáticamente.',
        request=CustomerAddressSerializer,
        responses={
            201: CustomerAddressSerializer,
            400: OpenApiResponse(description='Error de validación'),
        },
        tags=['customers'],
        examples=[
            OpenApiExample(
                'Nueva dirección',
                summary='Ejemplo de creación de dirección',
                description='Ejemplo de una solicitud para crear una nueva dirección',
                value={
                    'label': 'Casa',
                    'street_address': 'Av. Principal 123',
                    'city': 'Ciudad de México',
                    'state': 'CDMX',
                    'postal_code': '06600',
                    'country': 'México',
                    'is_default': True,
                },
                request_only=True,
            ),
        ],
    ),
)
class CustomerAddressListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear direcciones del cliente"""
    serializer_class = CustomerAddressSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        customer, created = Customer.objects.get_or_create(
            user=self.request.user
        )
        return customer.addresses.all()
    
    def perform_create(self, serializer):
        customer, created = Customer.objects.get_or_create(
            user=self.request.user
        )
        serializer.save(customer=customer)

@extend_schema_view(
    get=extend_schema(
        summary='Obtener dirección del cliente',
        description='Retorna los detalles de una dirección específica del cliente autenticado.',
        responses={200: CustomerAddressSerializer},
        tags=['customers'],
    ),
    put=extend_schema(
        summary='Actualizar dirección (completa)',
        description='Actualiza todos los campos de una dirección específica del cliente autenticado.',
        request=CustomerAddressSerializer,
        responses={200: CustomerAddressSerializer},
        tags=['customers'],
    ),
    patch=extend_schema(
        summary='Actualizar dirección (parcial)',
        description='Actualiza parcialmente los campos de una dirección específica del cliente autenticado.',
        request=CustomerAddressSerializer,
        responses={200: CustomerAddressSerializer},
        tags=['customers'],
    ),
    delete=extend_schema(
        summary='Eliminar dirección',
        description='Elimina una dirección específica del cliente autenticado.',
        responses={204: None},
        tags=['customers'],
    ),
)
class CustomerAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para ver, actualizar y eliminar direcciones específicas"""
    serializer_class = CustomerAddressSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        customer, created = Customer.objects.get_or_create(
            user=self.request.user
        )
        return customer.addresses.all()
