# core/middleware/location_tracking.py
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone


class LocationTrackingMiddleware(MiddlewareMixin):
    """Middleware para actualizar ubicación de repartidores y conductores"""

    def process_request(self, request):
        # Solo procesar si hay datos de ubicación en el request
        lat = request.META.get("HTTP_X_LATITUDE")
        lon = request.META.get("HTTP_X_LONGITUDE")

        if lat and lon and request.user.is_authenticated:
            # Actualizar ubicación de repartidor
            if hasattr(request.user, "delivery_profile"):
                delivery_person = request.user.delivery_profile
                delivery_person.current_latitude = lat
                delivery_person.current_longitude = lon
                delivery_person.last_location_update = timezone.now()
                delivery_person.save(update_fields=["current_latitude", "current_longitude", "last_location_update"])

            # Actualizar ubicación de conductor
            if hasattr(request.user, "driver_profile"):
                driver = request.user.driver_profile
                driver.current_latitude = lat
                driver.current_longitude = lon
                driver.last_location_update = timezone.now()
                driver.save(update_fields=["current_latitude", "current_longitude", "last_location_update"])

        return None
