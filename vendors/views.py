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
from .utils import haversine_distance
from customers.permissions import IsCustomer
from vendors.permissions import IsVendorOwner
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes



@extend_schema_view(
    list=extend_schema(
        summary='Listar categorías de comercios',
        description='Obtiene el listado de todas las categorías de comercios activas.',
        tags=['vendors'],
    ),
    retrieve=extend_schema(
        summary='Obtener categoría de comercio',
        description='Obtiene los detalles de una categoría específica por su ID.',
        tags=['vendors'],
    ),
)
class VendorCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para categorías de comercios (solo lectura)
    """
    queryset = VendorCategory.objects.filter(is_active=True)
    serializer_class = VendorCategorySerializer
    permission_classes = [AllowAny]

@extend_schema_view(
    list=extend_schema(
        summary='Listar comercios',
        description='Obtiene el listado de comercios aprobados. Soporta filtros por categoría, estado, disponibilidad, búsqueda y ordenamiento.',
        tags=['vendors'],
        parameters=[
            OpenApiParameter('category', OpenApiTypes.INT, description='Filtrar por ID de categoría'),
            OpenApiParameter('status', OpenApiTypes.STR, description='Filtrar por estado (approved, pending, rejected)'),
            OpenApiParameter('is_open', OpenApiTypes.BOOL, description='Filtrar por comercios abiertos/cerrados'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Buscar por nombre del comercio, descripción o categoría'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Ordenar por rating, delivery_time, delivery_fee, created_at. Prefijo - para descendente.'),
        ],
    ),
    create=extend_schema(
        summary='Registrar comercio',
        description='Registra un nuevo comercio asociado al usuario autenticado. El comercio quedará pendiente de aprobación.',
        request=VendorRegistrationSerializer,
        responses={201: VendorSerializer},
        tags=['vendors'],
    ),
    retrieve=extend_schema(
        summary='Obtener comercio',
        description='Obtiene los detalles completos de un comercio específico por su ID.',
        tags=['vendors'],
    ),
    update=extend_schema(
        summary='Actualizar comercio',
        description='Actualiza todos los datos de un comercio. Solo el propietario del comercio puede realizarlo.',
        request=VendorSerializer,
        tags=['vendors'],
    ),
    partial_update=extend_schema(
        summary='Actualizar parcialmente comercio',
        description='Actualiza parcialmente los datos de un comercio. Solo el propietario del comercio puede realizarlo.',
        request=VendorSerializer,
        tags=['vendors'],
    ),
    destroy=extend_schema(
        summary='Eliminar comercio',
        description='Elimina un comercio. Solo el propietario del comercio puede realizarlo.',
        tags=['vendors'],
    ),
)
class VendorViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para comercios
    """
    queryset = Vendor.objects.filter(status='approved')
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'status', 'is_open']
    search_fields = ['business_name', 'description', 'category__name']
    ordering_fields = ['rating', 'delivery_time', 'delivery_fee', 'created_at']
    ordering = ['-rating']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return VendorListSerializer
        elif self.action == 'create':
            return VendorRegistrationSerializer
        return VendorSerializer
    
    def get_permissions(self):
        """
        Permisos específicos por acción
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        elif self.action == 'create':
            permission_classes = [IsAuthenticated]
        elif self.action in ['products', 'ratings', 'nearby']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsVendorOwner]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """
        Asociar el vendor al usuario actual
        """
        serializer.save(user=self.request.user)
    
    @extend_schema(
        summary='Obtener productos de un comercio',
        description='Obtiene el listado de productos disponibles de un comercio específico. Soporta filtros opcionales por categoría y búsqueda por nombre o descripción.',
        tags=['vendors'],
        parameters=[
            OpenApiParameter('product_category', OpenApiTypes.STR, description='Filtrar productos por categoría'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Buscar productos por nombre o descripción'),
        ],
        responses={200: ProductSerializer(many=True)},
    )
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """
        Obtener productos de un comercio específico
        """
        vendor = self.get_object()
        products = vendor.products.filter(is_available=True)
        
        # Filtros opcionales (usar nombres distintos a filterset_fields para evitar conflictos)
        category = request.query_params.get('product_category')
        if category:
            products = products.filter(category__icontains=category)
        
        product_search = request.query_params.get('product_search')
        if product_search:
            products = products.filter(
                Q(name__icontains=product_search) | Q(description__icontains=product_search)
            )
        
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary='Obtener calificaciones de un comercio',
        description='Obtiene todas las calificaciones y comentarios de un comercio específico, ordenadas por fecha de creación descendente.',
        tags=['vendors'],
        responses={200: VendorRatingSerializer(many=True)},
    )
    @action(detail=True, methods=['get'])
    def ratings(self, request, pk=None):
        """
        Obtener calificaciones de un comercio
        """
        vendor = self.get_object()
        ratings = VendorRating.objects.filter(vendor=vendor).order_by('-created_at')
        serializer = VendorRatingSerializer(ratings, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary='Obtener comercios cercanos',
        description='Obtiene los comercios abiertos cercanos a una ubicación basada en coordenadas de latitud y longitud.',
        tags=['vendors'],
        parameters=[
            OpenApiParameter('latitude', OpenApiTypes.FLOAT, description='Latitud de la ubicación de referencia', required=True),
            OpenApiParameter('longitude', OpenApiTypes.FLOAT, description='Longitud de la ubicación de referencia', required=True),
        ],
        responses={200: VendorListSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """
        Obtener comercios cercanos basado en ubicación
        """
        lat = request.query_params.get('latitude')
        lng = request.query_params.get('longitude')
        
        if not lat or not lng:
            return Response(
                {'error': 'Se requieren parámetros latitude y longitude'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lat = float(lat)
            lng = float(lng)
        except (ValueError, TypeError):
            return Response(
                {'error': 'latitude y longitude deben ser valores numéricos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        vendors = self.get_queryset().filter(is_open=True)
        
        results = []
        for vendor in vendors:
            if vendor.latitude is not None and vendor.longitude is not None:
                distance = haversine_distance(lat, lng, vendor.latitude, vendor.longitude)
                if distance <= vendor.delivery_radius:
                    serializer = VendorListSerializer(vendor)
                    data = serializer.data
                    data['distance'] = distance
                    results.append(data)
        
        results.sort(key=lambda x: x['distance'])
        
        return Response(results)
    
    @extend_schema(
        summary='Abrir/cerrar comercio',
        description='Alterna el estado de apertura de un comercio (abierto/cerrado). Solo el propietario del comercio puede realizarlo.',
        tags=['vendors'],
        responses={
            200: OpenApiResponse(description='Estado actualizado correctamente'),
        },
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsVendorOwner])
    def toggle_status(self, request, pk=None):
        """
        Abrir/cerrar comercio
        """
        vendor = self.get_object()
        vendor.is_open = not vendor.is_open
        vendor.save()
        
        return Response({
            'status': 'abierto' if vendor.is_open else 'cerrado',
            'is_open': vendor.is_open
        })

@extend_schema_view(
    list=extend_schema(
        summary='Listar productos',
        description='Obtiene el listado de productos. Los comerciantes ven sus propios productos; los clientes ven los productos disponibles de comercios abiertos.',
        tags=['vendors'],
        parameters=[
            OpenApiParameter('vendor', OpenApiTypes.INT, description='Filtrar por ID del comercio'),
            OpenApiParameter('category', OpenApiTypes.STR, description='Filtrar por categoría del producto'),
            OpenApiParameter('is_available', OpenApiTypes.BOOL, description='Filtrar por disponibilidad'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Buscar por nombre o descripción'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Ordenar por price, times_ordered, created_at'),
        ],
    ),
    create=extend_schema(
        summary='Crear producto',
        description='Crea un nuevo producto asociado al comercio del usuario autenticado.',
        request=ProductCreateUpdateSerializer,
        responses={201: ProductSerializer},
        tags=['vendors'],
    ),
    retrieve=extend_schema(
        summary='Obtener producto',
        description='Obtiene los detalles de un producto específico por su ID.',
        tags=['vendors'],
    ),
    update=extend_schema(
        summary='Actualizar producto',
        description='Actualiza todos los datos de un producto. Solo el propietario del comercio puede realizarlo.',
        request=ProductCreateUpdateSerializer,
        tags=['vendors'],
    ),
    partial_update=extend_schema(
        summary='Actualizar parcialmente producto',
        description='Actualiza parcialmente los datos de un producto. Solo el propietario del comercio puede realizarlo.',
        request=ProductCreateUpdateSerializer,
        tags=['vendors'],
    ),
    destroy=extend_schema(
        summary='Eliminar producto',
        description='Elimina un producto. Solo el propietario del comercio puede realizarlo.',
        tags=['vendors'],
    ),
)
class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet para productos
    """
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['vendor', 'category', 'is_available']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'times_ordered', 'created_at']
    ordering = ['-times_ordered']
    
    def get_queryset(self):
        user = self.request.user
        if self.action == 'list':
            if hasattr(user, 'vendor_profile'):
                return Product.objects.filter(vendor=user.vendor_profile)
            # Customer/unauthenticated: only available products from open vendors
            return Product.objects.filter(is_available=True, vendor__is_open=True)
        # For detail/update/delete: allow lookup so IsVendorOwner can return 403
        return Product.objects.all()
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductCreateUpdateSerializer
        return ProductSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsVendorOwner]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        serializer.save(vendor=self.request.user.vendor_profile)

@extend_schema_view(
    list=extend_schema(
        summary='Listar calificaciones del cliente',
        description='Obtiene todas las calificaciones realizadas por el cliente autenticado.',
        tags=['vendors'],
    ),
    create=extend_schema(
        summary='Crear calificación',
        description='Crea una nueva calificación para un comercio. Solo clientes pueden calificar pedidos entregados.',
        request=VendorRatingCreateSerializer,
        responses={201: VendorRatingSerializer},
        tags=['vendors'],
    ),
    retrieve=extend_schema(
        summary='Obtener calificación',
        description='Obtiene los detalles de una calificación específica.',
        tags=['vendors'],
    ),
    update=extend_schema(
        summary='Actualizar calificación',
        description='Actualiza una calificación existente.',
        request=VendorRatingCreateSerializer,
        tags=['vendors'],
    ),
    partial_update=extend_schema(
        summary='Actualizar parcialmente calificación',
        description='Actualiza parcialmente una calificación existente.',
        request=VendorRatingCreateSerializer,
        tags=['vendors'],
    ),
    destroy=extend_schema(
        summary='Eliminar calificación',
        description='Elimina una calificación existente.',
        tags=['vendors'],
    ),
)
class VendorRatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet para calificaciones de comercios
    """
    serializer_class = VendorRatingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request.user, 'customer_profile'):
            return VendorRating.objects.filter(customer=self.request.user.customer_profile)
        return VendorRating.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return VendorRatingCreateSerializer
        return VendorRatingSerializer
    
    def get_permissions(self):
        permission_classes = [IsAuthenticated, IsCustomer]
        return [permission() for permission in permission_classes]