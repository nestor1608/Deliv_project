from decimal import Decimal
from rest_framework import generics, permissions, status, viewsets, filters
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from .models import Order, OrderStatusHistory
from .models.coupon import Coupon
from .serializers import OrderSerializer, OrderStatusHistorySerializer, CreateOrderSerializer, CouponSerializer
from .permissions import IsCustomer, IsVendor, IsOrderOwner
from .services import validate_and_apply_coupon
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

@extend_schema_view(
    get=extend_schema(
        summary='Listar pedidos del cliente',
        description='Obtiene el listado de pedidos realizados por el cliente autenticado, incluyendo items, productos e historial de estados.',
        tags=['orders'],
    ),
    post=extend_schema(
        summary='Crear pedido',
        description='Crea un nuevo pedido con los productos seleccionados. El pedido debe incluir al menos un producto y se calcularán automáticamente subtotal, impuestos y costo de envío.',
        request=CreateOrderSerializer,
        responses={201: OrderSerializer},
        tags=['orders'],
    ),
)
class OrderListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar pedidos del cliente actual y crear nuevos pedidos
    """
    permission_classes = [permissions.IsAuthenticated, IsCustomer]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateOrderSerializer
        return OrderSerializer
    
    def get_queryset(self):
        return Order.objects.filter(
            customer=self.request.user.customer_profile
        ).prefetch_related('items__product', 'status_history')
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        response_serializer = OrderSerializer(order, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

@extend_schema(
    summary='Obtener detalle del pedido',
    description='Obtiene los detalles completos de un pedido específico, incluyendo items, productos, información del cliente y del comercio, e historial de estados.',
    tags=['orders'],
)
class OrderDetailView(generics.RetrieveAPIView):
    """
    Vista para ver detalles de un pedido específico
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.prefetch_related(
            'items__product', 
            'status_history'
        )
    
    def get_object(self):
        """Filter by user's accessible orders so unauthorized access returns 404."""
        queryset = self.get_queryset()
        user = self.request.user
        
        if user.role == 'customer' and hasattr(user, 'customer_profile'):
            queryset = queryset.filter(customer=user.customer_profile)
        elif user.role == 'vendor' and hasattr(user, 'vendor_profile'):
            queryset = queryset.filter(vendor=user.vendor_profile)
        elif user.role == 'delivery':
            queryset = queryset.filter(delivery_person=user.delivery_profile)
        else:
            queryset = queryset.none()
        
        return get_object_or_404(queryset, pk=self.kwargs['pk'])

@extend_schema(
    summary='Listar pedidos del comercio',
    description='Obtiene el listado de pedidos recibidos por el comercio autenticado, incluyendo items, productos e historial de estados.',
    tags=['orders'],
)
class VendorOrdersView(generics.ListAPIView):
    """
    Vista para que los comercios vean sus propios pedidos
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendor]
    
    def get_queryset(self):
        return Order.objects.filter(
            vendor=self.request.user.vendor_profile
        ).prefetch_related('items__product', 'status_history')

@extend_schema(
    summary='Actualizar estado del pedido',
    description='Actualiza el estado de un pedido. Solo el comercio propietario del pedido puede realizarlo. Se guarda un registro en el historial de cambios con el estado anterior y el nuevo.',
    tags=['orders'],
    request=OpenApiTypes.OBJECT,
    parameters=[
        OpenApiParameter('order_id', OpenApiTypes.INT, location=OpenApiParameter.PATH, description='ID del pedido a actualizar'),
    ],
    responses={
        200: OrderSerializer,
        400: OpenApiResponse(description='Estado inválido'),
    },
)
@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated, IsVendor])
def update_order_status(request, order_id):
    """
    Endpoint para actualizar el estado de un pedido (solo comercios)
    """
    order = get_object_or_404(
        Order, 
        id=order_id, 
        vendor=request.user.vendor_profile
    )
    
    new_status = request.data.get('status')
    notes = request.data.get('notes', '')
    
    if not new_status or new_status not in dict(Order.STATUS_CHOICES):
        return Response(
            {'error': 'Estado inválido'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Guardar estado anterior
    previous_status = order.status
    
    # Actualizar pedido (el signal pre_save crea el OrderStatusHistory automáticamente)
    order.status = new_status
    order.save()
    
    return Response({
        'message': 'Estado actualizado correctamente',
        'order': OrderSerializer(order).data
    })

@extend_schema(
    summary='Seguimiento de pedido',
    description='Obtiene información de seguimiento en tiempo real de un pedido. Accesible para el cliente, el comercio o el repartidor asociado al pedido.',
    tags=['orders'],
    parameters=[
        OpenApiParameter('order_number', OpenApiTypes.STR, location=OpenApiParameter.PATH, description='Número único de pedido para seguimiento'),
    ],
    responses={
        200: OpenApiResponse(description='Datos de seguimiento del pedido'),
        404: OpenApiResponse(description='Pedido no encontrado'),
    },
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def order_tracking(request, order_number):
    """
    Vista para seguimiento en tiempo real del pedido
    """
    try:
        # Verificar que el usuario puede ver este pedido
        if request.user.role == 'customer':
            order = Order.objects.get(
                order_number=order_number,
                customer=request.user.customer_profile
            )
        elif request.user.role == 'vendor':
            order = Order.objects.get(
                order_number=order_number,
                vendor=request.user.vendor_profile
            )
        elif request.user.role == 'delivery':
            order = Order.objects.get(
                order_number=order_number,
                delivery_person=request.user.delivery_profile
            )
        else:
            return Response(
                {'error': 'Sin permisos para ver este pedido'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Datos de seguimiento
        tracking_data = {
            'order_number': order.order_number,
            'status': order.status,
            'status_display': order.get_status_display(),
            'estimated_delivery_time': order.estimated_delivery_time,
            'created_at': order.created_at,
            'updated_at': order.updated_at,
            'total_amount': order.total_amount,
            'delivery_address': order.delivery_address,
            'status_history': OrderStatusHistorySerializer(
                order.status_history.all(), 
                many=True
            ).data
        }
        
        return Response(tracking_data)
        
    except Order.DoesNotExist:
        return Response(
            {'error': 'Pedido no encontrado'}, 
            status=status.HTTP_404_NOT_FOUND
        )

class CouponViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD for coupons.
    """
    serializer_class = CouponSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Coupon.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'discount_type', 'vendor']
    search_fields = ['code', 'description']
    ordering_fields = ['created_at', 'valid_from', 'valid_to']
    ordering = ['-created_at']

@extend_schema(
    summary='Validar cupón',
    description='Valida un código de cupón y devuelve el descuento aplicable.',
    tags=['orders'],
    parameters=[
        OpenApiParameter(name='code', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=True),
        OpenApiParameter(name='subtotal', type=OpenApiTypes.NUMBER, location=OpenApiParameter.QUERY, required=True),
        OpenApiParameter(name='vendor_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
    ],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validate_coupon(request):
    code = request.query_params.get('code')
    subtotal = request.query_params.get('subtotal')
    vendor_id = request.query_params.get('vendor_id')
    
    if not code or not subtotal:
        return Response({'error': 'Faltan parámetros'}, status=400)
    
    try:
        subtotal = Decimal(subtotal)
    except:
        return Response({'error': 'Subtotal inválido'}, status=400)
    
    vendor = None
    if vendor_id:
        from vendors.models import Vendor
        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            pass
    
    result = validate_and_apply_coupon(code, subtotal, vendor, request.user)
    
    if result['success']:
        return Response({
            'valid': True,
            'discount_amount': float(result['discount_amount']),
            'message': result['message'],
        })
    else:
        return Response({
            'valid': False,
            'discount_amount': 0,
            'message': result['message'],
        })