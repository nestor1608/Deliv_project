import logging
from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task
def process_refund(refund_id):
    """
    Execute a refund via the payment gateway.
    Called after admin approves a refund.
    """
    from .models import Refund

    try:
        refund = Refund.objects.select_related("payment").get(id=refund_id)
    except Refund.DoesNotExist:
        logger.error(f"Refund {refund_id} not found")
        return {"error": "Refund not found"}

    if refund.status != "approved":
        logger.warning(f"Refund {refund_id} is not in approved status: {refund.status}")
        return {"error": f"Refund is {refund.status}, not approved"}

    refund.status = "processing"
    refund.save(update_fields=["status"])

    try:
        payment = refund.payment

        # Integrate with payment gateway (MercadoPago/Stripe)
        if payment.payment_method.provider == "mercadopago":
            from core.utils.payments import MercadoPagoService

            mp_service = MercadoPagoService()
            result = mp_service.create_refund(
                payment_id=payment.external_payment_id, amount=float(refund.amount), reason=refund.reason
            )
            if result.get("status") == "approved":
                refund.external_refund_id = result.get("id", "")
            else:
                raise Exception(result.get("status_detail", "Gateway error"))

        # Mark refund as completed
        refund.status = "completed"
        refund.completed_at = timezone.now()
        refund.save(update_fields=["status", "completed_at", "external_refund_id"])

        # Update parent payment status
        total_refunded = sum(r.amount for r in payment.refunds.filter(status="completed"))
        if total_refunded >= payment.amount:
            payment.status = "refunded"
        else:
            payment.status = "partially_refunded"
        payment.save(update_fields=["status"])

        logger.info(f"Refund {refund.refund_id} completed successfully")
        return {"status": "completed", "refund_id": refund.refund_id}

    except Exception as e:
        refund.status = "failed"
        refund.rejection_reason = str(e)
        refund.save(update_fields=["status", "rejection_reason"])
        logger.error(f"Refund {refund.refund_id} failed: {e}")
        return {"error": str(e)}


@shared_task
def reconcile_payments():
    """
    Periodic reconciliation task - marks stale pending payments as failed.
    """
    from .models import Payment

    cutoff = timezone.now() - timedelta(hours=24)

    stale = Payment.objects.filter(Q(status="pending") | Q(status="processing"), created_at__lt=cutoff)
    stale_count = stale.count()

    for payment in stale:
        payment.status = "failed"
        payment.failure_reason = "Auto-cancelado: tiempo de espera excedido (24h)"
        payment.save(update_fields=["status", "failure_reason", "updated_at"])

    completed_today = Payment.objects.filter(status="completed", completed_at__date=timezone.now().date()).count()

    logger.info(f"Reconciliation: {stale_count} stale failed, {completed_today} completed today")
    return {"stale_failed": stale_count, "completed_today": completed_today}
