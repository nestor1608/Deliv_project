from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from .models import *
from .serializers import *
from customers.permissions import IsCustomer

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from core.throttles import LocationRateThrottle


@extend_schema_view(
    list=extend_schema(
        summary="Listar repartidores",
        description="Obtiene la lista de repartidores según el perfil del usuario.",
        tags=["delivery"],
    ),
    create=extend_schema(
        summary="Crear repartidor",
        description="Registra un nuevo repartidor en el sistema.",
        tags=["delivery"],
    ),
    retrieve=extend_schema(
        summary="Obtener repartidor",
        description="Obtiene los detalles de un repartidor específico.",
        tags=["delivery"],
    ),
    update=extend_schema(
        summary="Actualizar repartidor",
        description="Actualiza los datos completos de un repartidor.",
        tags=["delivery"],
    ),
    partial_update=extend_schema(
        summary="Actualizar parcialmente repartidor",
        description="Actualiza parcialmente los datos de un repartidor.",
        tags=["delivery"],
    ),
)
class DeliveryPersonViewSet(viewsets.ModelViewSet):
    """
    ViewSet para repartidores
    """

    serializer_class = DeliveryPersonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, "delivery_profile"):
            return DeliveryPerson.objects.filter(user=self.request.user)
        return DeliveryPerson.objects.none()

    def get_serializer_class(self):
        if self.action == "create":
            return DeliveryPersonRegistrationSerializer
        return DeliveryPersonSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        summary="Actualizar ubicación",
        description="Actualiza la ubicación geográfica del repartidor.",
        tags=["delivery"],
        request=DeliveryLocationUpdateSerializer,
        responses={200: OpenApiResponse(description="Ubicación actualizada correctamente")},
    )
    @action(detail=True, methods=["patch"], throttle_classes=[LocationRateThrottle])
    def update_location(self, request, pk=None):
        """
        Actualizar ubicación del repartidor
        """
        delivery_person = self.get_object()
        serializer = DeliveryLocationUpdateSerializer(delivery_person, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"message": "Ubicación actualizada correctamente"})

    @extend_schema(
        summary="Cambiar disponibilidad",
        description="Cambia la disponibilidad actual del repartidor.",
        tags=["delivery"],
        request=DeliveryAvailabilitySerializer,
        responses={200: OpenApiResponse(description="Disponibilidad actualizada")},
    )
    @action(detail=True, methods=["patch"])
    def update_availability(self, request, pk=None):
        """
        Cambiar disponibilidad del repartidor
        """
        delivery_person = self.get_object()
        new_availability = request.data.get("availability")

        # Block going online if KYC not approved
        if new_availability == "available" and delivery_person.background_check_status != "approved":
            return Response({"error": "Debes completar la verificación KYC antes de estar disponible"}, status=400)

        serializer = DeliveryAvailabilitySerializer(delivery_person, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"message": "Disponibilidad actualizada", "availability": delivery_person.availability})

    @extend_schema(
        summary="Pedidos activos",
        description="Obtiene los pedidos activos asignados al repartidor.",
        tags=["delivery"],
        responses={200: OrderSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def active_orders(self, request, pk=None):
        """
        Obtener pedidos activos del repartidor
        """
        delivery_person = self.get_object()
        orders = Order.objects.filter(delivery_person=delivery_person, status__in=["picked_up", "ready"]).order_by(
            "-created_at"
        )

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Ganancias del repartidor",
        description="Obtiene las ganancias totales del repartidor con filtros opcionales por fecha.",
        tags=["delivery"],
        parameters=[
            OpenApiParameter(
                name="from_date", description="Fecha inicial (YYYY-MM-DD)", required=False, type=OpenApiTypes.DATE
            ),
            OpenApiParameter(
                name="to_date", description="Fecha final (YYYY-MM-DD)", required=False, type=OpenApiTypes.DATE
            ),
        ],
        responses={200: OpenApiResponse(description="Ganancias del repartidor")},
    )
    @action(detail=True, methods=["get"])
    def earnings(self, request, pk=None):
        """
        Obtener ganancias del repartidor
        """
        delivery_person = self.get_object()

        # Filtros de fecha opcionales
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")

        orders = Order.objects.filter(delivery_person=delivery_person, status="delivered")

        if from_date:
            orders = orders.filter(delivered_at__gte=from_date)
        if to_date:
            orders = orders.filter(delivered_at__lte=to_date)

        total_earnings = sum(order.delivery_fee for order in orders)
        total_deliveries = orders.count()

        return Response(
            {
                "total_earnings": total_earnings,
                "total_deliveries": total_deliveries,
                "average_per_delivery": total_earnings / total_deliveries if total_deliveries else 0,
            }
        )

    @extend_schema(
        summary="Subir documentos KYC",
        description="Sube los documentos de identidad y selfie para verificación.",
        tags=["delivery"],
    )
    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload_kyc(self, request, pk=None):
        delivery_person = self.get_object()

        if delivery_person.user != request.user:
            return Response({"error": "No puedes modificar este perfil"}, status=403)

        for field in ["id_document_front", "id_document_back", "selfie"]:
            if field in request.FILES:
                setattr(delivery_person, field, request.FILES[field])

        delivery_person.background_check_status = "pending"
        delivery_person.kyc_submitted_at = timezone.now()
        delivery_person.save()

        return Response(
            {
                "message": "Documentos subidos correctamente",
                "background_check_status": delivery_person.background_check_status,
            }
        )

    @extend_schema(
        summary="Aprobar KYC",
        description="Aprueba la verificación KYC de un repartidor. Solo admin.",
        tags=["delivery"],
    )
    @action(detail=True, methods=["post"])
    def approve_kyc(self, request, pk=None):
        if request.user.role != "admin":
            return Response({"error": "Solo administradores"}, status=403)

        delivery_person = self.get_object()
        delivery_person.background_check_status = "approved"
        delivery_person.kyc_verified_at = timezone.now()
        delivery_person.status = "approved"
        delivery_person.save()

        return Response({"message": "KYC aprobado", "status": "approved"})

    @extend_schema(
        summary="Rechazar KYC",
        description="Rechaza la verificación KYC de un repartidor. Solo admin.",
        tags=["delivery"],
    )
    @action(detail=True, methods=["post"])
    def reject_kyc(self, request, pk=None):
        if request.user.role != "admin":
            return Response({"error": "Solo administradores"}, status=403)

        delivery_person = self.get_object()
        delivery_person.background_check_status = "rejected"
        delivery_person.kyc_verified_at = None
        delivery_person.save()

        return Response({"message": "KYC rechazado", "status": "rejected"})


@extend_schema_view(
    list=extend_schema(
        summary="Listar calificaciones",
        description="Obtiene la lista de calificaciones de repartidores para el cliente autenticado.",
        tags=["delivery"],
    ),
    create=extend_schema(
        summary="Crear calificación",
        description="Crea una nueva calificación para un repartidor.",
        tags=["delivery"],
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
        if hasattr(self.request.user, "customer_profile"):
            return DeliveryRating.objects.filter(customer=self.request.user.customer_profile)
        return DeliveryRating.objects.none()

    def get_serializer_class(self):
        if self.action == "create":
            return DeliveryRatingCreateSerializer
        return DeliveryRatingSerializer

    def get_permissions(self):
        permission_classes = [IsAuthenticated, IsCustomer]
        return [permission() for permission in permission_classes]
