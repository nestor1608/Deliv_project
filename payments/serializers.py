from rest_framework import serializers
from .models import Payment, PaymentMethod, Refund
from django.contrib.contenttypes.models import ContentType
from orders.models import Order
from mobility.models import Trip


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer para métodos de pago"""

    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = PaymentMethod
        fields = ["id", "name", "type", "type_display", "provider", "is_active", "commission_percentage"]


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer completo para pagos"""

    payment_method_info = PaymentMethodSerializer(source="payment_method", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    user_info = serializers.SerializerMethodField()
    object_info = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "payment_id",
            "external_payment_id",
            "user_info",
            "payment_method_info",
            "object_info",
            "amount",
            "commission",
            "net_amount",
            "status",
            "status_display",
            "metadata",
            "failure_reason",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "payment_id",
            "user_info",
            "payment_method_info",
            "object_info",
            "commission",
            "net_amount",
            "status_display",
            "created_at",
            "updated_at",
            "completed_at",
        ]

    def get_user_info(self, obj):
        return {"id": obj.user.id, "name": obj.user.get_full_name(), "email": obj.user.email}

    def get_object_info(self, obj):
        """Información del objeto pagado (pedido o viaje)"""
        if obj.content_object:
            if isinstance(obj.content_object, Order):
                return {
                    "type": "order",
                    "id": obj.content_object.id,
                    "number": obj.content_object.order_number,
                    "vendor": obj.content_object.vendor.business_name,
                    "total_amount": obj.content_object.total_amount,
                }
            elif isinstance(obj.content_object, Trip):
                return {
                    "type": "trip",
                    "id": obj.content_object.id,
                    "number": obj.content_object.trip_number,
                    "pickup": obj.content_object.pickup_address,
                    "destination": obj.content_object.destination_address,
                    "total_fare": obj.content_object.total_fare,
                }
        return None


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear pagos"""

    object_type = serializers.ChoiceField(choices=[("order", "Pedido"), ("trip", "Viaje")], write_only=True)
    object_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Payment
        fields = ["object_type", "object_id", "payment_method", "metadata"]

    def validate(self, attrs):
        object_type = attrs["object_type"]
        object_id = attrs["object_id"]
        request = self.context["request"]

        # Validar que el objeto existe y pertenece al usuario
        if object_type == "order":
            try:
                order = Order.objects.get(id=object_id)
                if order.customer.user != request.user:
                    raise serializers.ValidationError("No puedes pagar este pedido")
                attrs["content_object"] = order
                attrs["amount"] = order.total_amount
            except Order.DoesNotExist:
                raise serializers.ValidationError("Pedido no encontrado")

        elif object_type == "trip":
            try:
                trip = Trip.objects.get(id=object_id)
                if trip.customer.user != request.user:
                    raise serializers.ValidationError("No puedes pagar este viaje")
                attrs["content_object"] = trip
                attrs["amount"] = trip.total_fare
            except Trip.DoesNotExist:
                raise serializers.ValidationError("Viaje no encontrado")

        # Verificar que no haya un pago exitoso previo
        content_type = ContentType.objects.get_for_model(attrs["content_object"])
        existing_payment = Payment.objects.filter(
            content_type=content_type, object_id=object_id, status="completed"
        ).first()

        if existing_payment:
            raise serializers.ValidationError("Este objeto ya ha sido pagado")

        return attrs

    def create(self, validated_data):
        content_object = validated_data.pop("content_object")
        validated_data.pop("object_type")
        validated_data.pop("object_id")

        return Payment.objects.create(
            user=self.context["request"].user, content_object=content_object, **validated_data
        )


class RefundSerializer(serializers.ModelSerializer):
    """Serializer para reembolsos"""

    payment_info = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Refund
        fields = [
            "id",
            "refund_id",
            "external_refund_id",
            "payment_info",
            "amount",
            "reason",
            "status",
            "status_display",
            "created_at",
            "completed_at",
        ]
        read_only_fields = ["id", "refund_id", "payment_info", "status_display", "created_at", "completed_at"]

    def get_payment_info(self, obj):
        return {
            "payment_id": obj.payment.payment_id,
            "original_amount": obj.payment.amount,
            "payment_method": obj.payment.payment_method.name,
        }


class RefundCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear reembolsos"""

    class Meta:
        model = Refund
        fields = ["payment", "amount", "reason"]

    def validate(self, attrs):
        payment = attrs["payment"]
        amount = attrs["amount"]

        # Verificar que el pago esté completado
        if payment.status != "completed":
            raise serializers.ValidationError("Solo se pueden reembolsar pagos completados")

        # Verificar que no exceda el monto original
        if amount > payment.amount:
            raise serializers.ValidationError("El monto de reembolso no puede ser mayor al pago original")

        # Verificar que no haya reembolsos pendientes
        if payment.refunds.filter(status__in=["pending", "processing"]).exists():
            raise serializers.ValidationError("Ya hay un reembolso en proceso para este pago")

        return attrs


class ProcessPaymentSerializer(serializers.Serializer):
    """Serializer para procesar pagos"""

    object_type = serializers.ChoiceField(choices=[("order", "Pedido"), ("trip", "Viaje")])
    object_id = serializers.IntegerField()
    payment_method_id = serializers.IntegerField()
    payment_data = serializers.JSONField(required=False, default=dict)

    def validate_payment_method_id(self, value):
        try:
            PaymentMethod.objects.get(id=value, is_active=True)
            return value
        except PaymentMethod.DoesNotExist:
            raise serializers.ValidationError("Método de pago no válido")


class PaymentStatsSerializer(serializers.Serializer):
    """Serializer para estadísticas de pagos"""

    total_payments = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    completed_payments = serializers.IntegerField()
    pending_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()
    this_month = serializers.IntegerField()
    by_method = serializers.ListSerializer(child=serializers.DictField(), read_only=True)


class PaymentReceiptSerializer(serializers.Serializer):
    """Serializer para recibos de pago"""

    payment_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    commission = serializers.DecimalField(max_digits=10, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_method = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)
    user = serializers.DictField()
    order = serializers.DictField(required=False)
    trip = serializers.DictField(required=False)
