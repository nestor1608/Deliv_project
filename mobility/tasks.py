import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def assignment_timeout(self, trip_id):
    """
    Celery task that cancels a trip if no driver has accepted it within the timeout period.
    Scheduled when a trip is created with status 'requested'.
    """
    from mobility.models import Trip

    try:
        trip = Trip.objects.get(id=trip_id)
    except Trip.DoesNotExist:
        logger.warning(f"Trip {trip_id} not found for assignment timeout")
        return {"status": "not_found", "trip_id": trip_id}

    # Only cancel if still 'requested' (no driver accepted yet)
    if trip.status == "requested":
        trip.status = "cancelled_no_driver"
        trip.cancelled_at = timezone.now()
        trip.cancellation_reason = "Tiempo de espera agotado - no se encontró conductor"
        trip.save()
        logger.info(f"Trip {trip.trip_number} cancelled due to assignment timeout")
        return {
            "status": "cancelled",
            "trip_id": trip_id,
            "trip_number": trip.trip_number,
        }

    # If already accepted or other status, do nothing
    logger.info(f"Trip {trip.trip_number} already has status '{trip.status}', skipping timeout")
    return {"status": "skipped", "trip_id": trip_id, "current_status": trip.status}
