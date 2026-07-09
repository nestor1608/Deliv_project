from rest_framework import viewsets, status, filters
from django.db import models
from django.conf import settings
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import json
import hashlib
import hmac

from .models import Payment, PaymentMethod, Refund
from .serializers import (
    PaymentSerializer,
    PaymentCreateSerializer,
    PaymentMethodSerializer,
    RefundSerializer,
    RefundCreateSerializer,
    ProcessPaymentSerializer,
)
from orders.models import Order
from mobility.models import Trip
from core.utils.payments import MercadoPagoService

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes


@extend_schema_view(
    list=extend_schema(
        summary="Listar métodos de pago",
        description="Obtiene la lista de métodos de pago disponibles y activos.",
        tags=["payments"],
    ),
    retrieve=extend_schema(
        summary="Obtener método de pago",
        description="Obtiene los detalles de un método de pago específico.",
        tags=["payments"],
    ),
)
class PaymentMethodViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para métodos de pago (solo lectura)
    """

    queryset = PaymentMethod.objects.filter(is_active=True)
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["type", "provider"]
    search_fields = ["name", "provider"]
    ordering = ["name"]


@extend_schema_view(
    list=extend_schema(
        summary="Listar pagos",
        description="Obtiene la lista de pagos del usuario autenticado.",
        tags=["payments"],
    ),
    create=extend_schema(
        summary="Crear pago",
        description="Registra un nuevo pago en el sistema.",
        tags=["payments"],
    ),
    retrieve=extend_schema(
        summary="Obtener pago",
        description="Obtiene los detalles de un pago específico.",
        tags=["payments"],
    ),
    update=extend_schema(
        summary="Actualizar pago",
        description="Actualiza los datos completos de un pago.",
        tags=["payments"],
    ),
    partial_update=extend_schema(
        summary="Actualizar parcialmente pago",
        description="Actualiza parcialmente los datos de un pago.",
        tags=["payments"],
    ),
    destroy=extend_schema(
        summary="Eliminar pago",
        description="Elimina un registro de pago del sistema.",
        tags=["payments"],
    ),
)
class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet para pagos
    """

    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "payment_method", "content_type"]
    search_fields = ["payment_id", "external_payment_id"]
    ordering_fields = ["created_at", "amount", "completed_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Los usuarios solo ven sus propios pagos
        if self.request.user.role == "admin":
            return Payment.objects.all()
        return Payment.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentCreateSerializer
        return PaymentSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @extend_schema(
        summary="Reembolsar pago",
        description="Crea una solicitud de reembolso para un pago completado.",
        tags=["payments"],
        responses={200: OpenApiResponse(description="Reembolso creado correctamente")},
    )
    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        """Crear reembolso para un pago"""
        payment = self.get_object()

        # Verificar que el pago esté completado
        if payment.status != "completed":
            return Response(
                {"error": "Solo se pueden reembolsar pagos completados"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar que no tenga reembolsos pendientes
        if payment.refunds.filter(status__in=["pending", "processing"]).exists():
            return Response(
                {"error": "Ya hay un reembolso en proceso para este pago"}, status=status.HTTP_400_BAD_REQUEST
            )

        amount = request.data.get("amount", payment.amount)
        # Convertir a Decimal si viene como string desde request.data
        if isinstance(amount, str):
            from decimal import Decimal, InvalidOperation

            try:
                amount = Decimal(amount)
            except InvalidOperation:
                return Response({"error": "Monto inválido"}, status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get("reason", "Reembolso solicitado por usuario")

        # Validar monto
        if amount > payment.amount:
            return Response(
                {"error": "El monto de reembolso no puede ser mayor al pago original"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Crear reembolso
        refund = Refund.objects.create(payment=payment, amount=amount, reason=reason, status="pending")

        # TODO: Integrar con API de proveedor de pagos para procesar reembolso

        return Response({"message": "Reembolso creado correctamente", "refund": RefundSerializer(refund).data})

    @extend_schema(
        summary="Obtener recibo",
        description="Obtiene el recibo o comprobante de un pago realizado.",
        tags=["payments"],
        responses={200: OpenApiResponse(description="Datos del recibo de pago")},
    )
    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        """Obtener recibo/comprobante del pago"""
        payment = self.get_object()

        # Datos del recibo
        receipt_data = {
            "payment_id": payment.payment_id,
            "amount": payment.amount,
            "commission": payment.commission,
            "net_amount": payment.net_amount,
            "payment_method": payment.payment_method.name,
            "status": payment.get_status_display(),
            "created_at": payment.created_at,
            "completed_at": payment.completed_at,
            "user": {"name": payment.user.get_full_name(), "email": payment.user.email},
        }

        # Agregar información del objeto pagado
        if payment.content_object:
            if isinstance(payment.content_object, Order):
                receipt_data["order"] = {
                    "order_number": payment.content_object.order_number,
                    "vendor": payment.content_object.vendor.business_name,
                    "items_count": payment.content_object.items.count(),
                }
            elif isinstance(payment.content_object, Trip):
                receipt_data["trip"] = {
                    "trip_number": payment.content_object.trip_number,
                    "pickup_address": payment.content_object.pickup_address,
                    "destination_address": payment.content_object.destination_address,
                }

        return Response(receipt_data)

    @extend_schema(
        summary="Estadísticas de pagos",
        description="Obtiene estadísticas de los pagos realizados por el usuario.",
        tags=["payments"],
        responses={200: OpenApiResponse(description="Estadísticas de pagos")},
    )
    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Estadísticas de pagos del usuario"""
        user_payments = self.get_queryset()

        stats = {
            "total_payments": user_payments.count(),
            "total_amount": user_payments.filter(status="completed").aggregate(total=Sum("amount"))["total"] or 0,
            "completed_payments": user_payments.filter(status="completed").count(),
            "pending_payments": user_payments.filter(status="pending").count(),
            "failed_payments": user_payments.filter(status="failed").count(),
            "this_month": user_payments.filter(
                created_at__month=timezone.now().month, created_at__year=timezone.now().year
            ).count(),
        }

        # Pagos por método
        by_method = (
            user_payments.values("payment_method__name")
            .annotate(count=models.Count("id"), total_amount=Sum("amount"))
            .order_by("-count")
        )

        stats["by_method"] = list(by_method)

        return Response(stats)


@extend_schema_view(
    list=extend_schema(
        summary="Listar reembolsos",
        description="Obtiene la lista de reembolsos del usuario autenticado.",
        tags=["payments"],
    ),
    create=extend_schema(
        summary="Crear reembolso",
        description="Crea una nueva solicitud de reembolso.",
        tags=["payments"],
    ),
    retrieve=extend_schema(
        summary="Obtener reembolso",
        description="Obtiene los detalles de un reembolso específico.",
        tags=["payments"],
    ),
)
class RefundViewSet(viewsets.ModelViewSet):
    """
    ViewSet para reembolsos
    """

    serializer_class = RefundSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "amount"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Los usuarios solo ven reembolsos de sus propios pagos
        if self.request.user.role == "admin":
            return Refund.objects.all()
        return Refund.objects.filter(payment__user=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return RefundCreateSerializer
        return RefundSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAuthenticated, IsAdminUser]  # Solo admins pueden gestionar reembolsos directamente
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @extend_schema(
        summary="Aprobar reembolso",
        description="Aprueba un reembolso pendiente y lo envía a procesar. Solo administradores.",
        tags=["payments"],
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiResponse(description="Reembolso aprobado")},
    )
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Aprobar reembolso pendiente (solo admin)"""
        if request.user.role != "admin":
            return Response(
                {"error": "Solo administradores pueden aprobar reembolsos"}, status=status.HTTP_403_FORBIDDEN
            )

        refund = self.get_object()

        if refund.status != "pending":
            return Response(
                {"error": f"El reembolso está en estado {refund.status}, no pendiente"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refund.status = "approved"
        refund.approved_by = request.user
        refund.save(update_fields=["status", "approved_by"])

        # Dispatch Celery task to process refund
        from .tasks import process_refund

        process_refund.delay(refund.id)

        return Response({"message": "Reembolso aprobado y enviado a procesar", "refund": RefundSerializer(refund).data})

    @extend_schema(
        summary="Rechazar reembolso",
        description="Rechaza un reembolso pendiente. Solo administradores.",
        tags=["payments"],
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiResponse(description="Reembolso rechazado")},
    )
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Rechazar reembolso (solo admin)"""
        if request.user.role != "admin":
            return Response(
                {"error": "Solo administradores pueden rechazar reembolsos"}, status=status.HTTP_403_FORBIDDEN
            )

        refund = self.get_object()

        if refund.status != "pending":
            return Response(
                {"error": f"El reembolso está en estado {refund.status}, no pendiente"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = request.data.get("reason", "Rechazado por administrador")

        refund.status = "failed"
        refund.rejected_at = timezone.now()
        refund.rejection_reason = reason
        refund.save(update_fields=["status", "rejected_at", "rejection_reason"])

        return Response({"message": "Reembolso rechazado", "refund": RefundSerializer(refund).data})


@extend_schema(
    summary="Procesar pago",
    description="Procesa un pago para un pedido o viaje usando el método de pago seleccionado.",
    tags=["payments"],
    request=ProcessPaymentSerializer,
    responses={200: OpenApiResponse(description="Resultado del procesamiento del pago")},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def process_payment(request):
    """
    Procesar un pago
    """
    serializer = ProcessPaymentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Datos del pago
    object_type = serializer.validated_data["object_type"]
    object_id = serializer.validated_data["object_id"]
    payment_method_id = serializer.validated_data["payment_method_id"]
    payment_data = serializer.validated_data.get("payment_data", {})

    try:
        # Obtener el objeto a pagar
        if object_type == "order":
            content_object = get_object_or_404(Order, id=object_id)
            amount = content_object.total_amount
        elif object_type == "trip":
            content_object = get_object_or_404(Trip, id=object_id)
            amount = content_object.total_fare
        else:
            return Response({"error": "Tipo de objeto no válido"}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar que el usuario puede pagar este objeto
        if object_type == "order" and content_object.customer.user != request.user:
            return Response({"error": "No puedes pagar este pedido"}, status=status.HTTP_403_FORBIDDEN)
        elif object_type == "trip" and content_object.customer.user != request.user:
            return Response({"error": "No puedes pagar este viaje"}, status=status.HTTP_403_FORBIDDEN)

        # Obtener método de pago
        payment_method = get_object_or_404(PaymentMethod, id=payment_method_id)

        # Verificar que no haya un pago exitoso previo
        content_type = ContentType.objects.get_for_model(content_object)
        existing_payment = Payment.objects.filter(
            content_type=content_type, object_id=object_id, status="completed"
        ).first()

        if existing_payment:
            return Response({"error": "Este objeto ya ha sido pagado"}, status=status.HTTP_400_BAD_REQUEST)

        # Crear registro de pago
        payment = Payment.objects.create(
            user=request.user,
            payment_method=payment_method,
            content_object=content_object,
            amount=amount,
            status="pending",
        )

        # Procesar según el método de pago
        if payment_method.type == "cash":
            # Efectivo - marcar como completado inmediatamente
            payment.status = "completed"
            payment.completed_at = timezone.now()
            payment.save()

            # Actualizar estado del objeto
            if object_type == "order":
                content_object.payment_status = "paid"
                content_object.save()
            elif object_type == "trip":
                content_object.payment_status = "paid"
                content_object.save()

            result = {"success": True, "message": "Pago en efectivo registrado", "payment_id": payment.payment_id}

        elif payment_method.provider == "mercadopago":
            # Procesar con MercadoPago
            mp_service = MercadoPagoService()

            mp_response = mp_service.create_payment(
                amount=float(amount),
                description=f"Pago {object_type} #{content_object.id}",
                payment_method_id=payment_data.get("payment_method_id"),
                email=request.user.email,
            )

            if mp_response.get("status") == "approved":
                payment.external_payment_id = mp_response.get("id")
                payment.status = "completed"
                payment.completed_at = timezone.now()
                payment.save()

                # Actualizar objeto
                if object_type == "order":
                    content_object.payment_status = "paid"
                    content_object.save()
                elif object_type == "trip":
                    content_object.payment_status = "paid"
                    content_object.save()

                result = {
                    "success": True,
                    "message": "Pago procesado exitosamente",
                    "payment_id": payment.payment_id,
                    "external_id": mp_response.get("id"),
                }
            else:
                payment.status = "failed"
                payment.failure_reason = mp_response.get("status_detail", "Error desconocido")
                payment.save()

                result = {
                    "success": False,
                    "message": "Error procesando el pago",
                    "error": mp_response.get("status_detail"),
                }

        else:
            # Método no implementado
            payment.status = "failed"
            payment.failure_reason = "Método de pago no implementado"
            payment.save()

            result = {"success": False, "message": "Método de pago no disponible"}

        return Response({**result, "payment": PaymentSerializer(payment).data})

    except Exception as e:
        return Response({"error": f"Error procesando el pago: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Webhook MercadoPago",
    description="Endpoint para recibir notificaciones de eventos de pago desde MercadoPago.",
    tags=["payments"],
    request=OpenApiTypes.OBJECT,
    responses={200: OpenApiResponse(description="OK"), 401: OpenApiResponse(description="Firma inválida")},
)
@csrf_exempt
@api_view(["POST"])
@permission_classes([])  # Sin autenticación para webhooks
def mercadopago_webhook(request):
    """
    Webhook para notificaciones de MercadoPago
    """
    try:
        # Verificar firma del webhook (opcional pero recomendado)
        webhook_secret = settings.PAYMENT_SETTINGS["MERCADOPAGO"]["WEBHOOK_SECRET"]
        if webhook_secret:
            signature = request.META.get("HTTP_X_SIGNATURE")
            expected_signature = hmac.new(webhook_secret.encode(), request.body, hashlib.sha256).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                return HttpResponse(status=401)

        # Procesar notificación
        data = json.loads(request.body)
        payment_id = data.get("data", {}).get("id")

        if payment_id:
            # Consultar estado del pago en MercadoPago
            mp_service = MercadoPagoService()
            payment_info = mp_service.get_payment_status(payment_id)

            # Buscar pago en nuestra base de datos
            try:
                payment = Payment.objects.get(external_payment_id=payment_id)

                # Actualizar estado según respuesta de MP
                if payment_info.get("status") == "approved":
                    payment.status = "completed"
                    payment.completed_at = timezone.now()
                elif payment_info.get("status") in ["rejected", "cancelled"]:
                    payment.status = "failed"
                    payment.failure_reason = payment_info.get("status_detail")

                payment.save()

                # Actualizar objeto relacionado si el pago fue exitoso
                if payment.status == "completed" and payment.content_object:
                    if isinstance(payment.content_object, Order):
                        payment.content_object.payment_status = "paid"
                        payment.content_object.save()
                    elif isinstance(payment.content_object, Trip):
                        payment.content_object.payment_status = "paid"
                        payment.content_object.save()

            except Payment.DoesNotExist:
                pass  # Pago no encontrado, ignorar

        return HttpResponse(status=200)

    except Exception:
        return HttpResponse(status=500)


@extend_schema(
    summary="Webhook Stripe",
    description="Endpoint para recibir notificaciones de eventos de pago desde Stripe.",
    tags=["payments"],
    request=OpenApiTypes.OBJECT,
    responses={200: OpenApiResponse(description="OK")},
)
@csrf_exempt
@api_view(["POST"])
@permission_classes([])
def stripe_webhook(request):
    """
    Webhook para notificaciones de Stripe
    """
    try:
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        if not sig_header:
            return HttpResponse(status=400)

        webhook_secret = settings.PAYMENT_SETTINGS.get('STRIPE', {}).get('WEBHOOK_SECRET', '')
        if not webhook_secret:
            return HttpResponse(status=501)  # Not implemented

        # TODO: Implement full Stripe webhook verification
        # event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)

        return HttpResponse(status=200)
    except Exception:
        return HttpResponse(status=400)


@extend_schema(
    summary="Analíticas de pagos",
    description="Obtiene analíticas detalladas de pagos para administradores.",
    tags=["payments"],
    parameters=[
        OpenApiParameter(
            name="days", description="Número de días a analizar (default: 30)", required=False, type=OpenApiTypes.INT
        ),
    ],
    responses={200: OpenApiResponse(description="Analíticas de pagos")},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def payment_analytics(request):
    """
    Analíticas de pagos para administradores
    """
    from datetime import timedelta

    # Período de análisis
    days = int(request.query_params.get("days", 30))
    start_date = timezone.now() - timedelta(days=days)

    payments = Payment.objects.filter(created_at__gte=start_date)

    analytics = {
        "total_payments": payments.count(),
        "completed_payments": payments.filter(status="completed").count(),
        "total_revenue": payments.filter(status="completed").aggregate(total=Sum("amount"))["total"] or 0,
        "total_commission": payments.filter(status="completed").aggregate(total=Sum("commission"))["total"] or 0,
        "failed_payments": payments.filter(status="failed").count(),
        "pending_payments": payments.filter(status="pending").count(),
    }

    # Por método de pago
    by_method = (
        payments.filter(status="completed")
        .values("payment_method__name")
        .annotate(count=models.Count("id"), total_amount=Sum("amount"))
        .order_by("-total_amount")
    )

    analytics["by_method"] = list(by_method)

    # Por día (últimos 7 días)
    daily_stats = []
    for i in range(7):
        date = timezone.now().date() - timedelta(days=i)
        day_payments = payments.filter(created_at__date=date)
        daily_stats.append(
            {
                "date": date,
                "count": day_payments.count(),
                "amount": day_payments.filter(status="completed").aggregate(total=Sum("amount"))["total"] or 0,
            }
        )

    analytics["daily_stats"] = daily_stats

    return Response(analytics)


@extend_schema(
    summary="Simular pago",
    description="Simula el procesamiento de un pago para fines de prueba (solo disponible en modo DEBUG).",
    tags=["payments"],
    responses={200: OpenApiResponse(description="Resultado de la simulación")},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def simulate_payment(request):
    """
    Simular pago para testing (solo en modo DEBUG)
    """
    from django.conf import settings

    if not settings.DEBUG:
        return Response({"error": "Solo disponible en modo desarrollo"}, status=status.HTTP_403_FORBIDDEN)

    object_type = request.data.get("object_type")
    object_id = request.data.get("object_id")
    success = request.data.get("success", True)

    # Simular procesamiento de pago
    if success:
        return Response(
            {
                "success": True,
                "message": "Pago simulado exitosamente",
                "payment_id": f"SIM-{object_type.upper()}-{object_id}",
                "simulation": True,
            }
        )
    else:
        return Response(
            {
                "success": False,
                "message": "Pago simulado falló",
                "error": "Error simulado para testing",
                "simulation": True,
            }
        )
