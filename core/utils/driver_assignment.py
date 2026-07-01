# core/utils/driver_assignment.py
from mobility.models import Driver
from .location import calculate_distance

class DriverAssignmentService:
    """Servicio para asignar conductores a viajes"""
    
    @staticmethod
    def find_nearest_driver(pickup_lat, pickup_lon, max_distance_km=15):
        """Encontrar conductor más cercano al punto de recogida"""
        available_drivers = Driver.objects.filter(
            status='approved',
            availability='available',
            current_latitude__isnull=False,
            current_longitude__isnull=False
        )
        
        candidates = []
        
        for driver in available_drivers:
            distance = calculate_distance(
                pickup_lat, pickup_lon,
                driver.current_latitude,
                driver.current_longitude
            )
            
            if distance <= max_distance_km:
                candidates.append({
                    'driver': driver,
                    'distance': distance,
                    'rating': driver.rating
                })
        
        if not candidates:
            return None
        
        # Ordenar por distancia y rating
        candidates.sort(key=lambda x: (x['distance'], -x['rating']))
        return candidates[0]['driver']
    
    @staticmethod
    def assign_trip_to_driver(trip):
        """Asignar viaje a conductor disponible"""
        driver = DriverAssignmentService.find_nearest_driver(
            trip.pickup_latitude,
            trip.pickup_longitude
        )
        
        if driver:
            trip.driver = driver
            driver.availability = 'busy'
            driver.save()
            trip.save()
            
            # Enviar notificación al conductor
            from .notifications import FCMService
            fcm_service = FCMService()
            fcm_service.send_notification(
                driver.user,
                'Nuevo viaje asignado',
                f'Viaje desde {trip.pickup_address}',
                {
                    'trip_id': trip.id,
                    'trip_number': trip.trip_number,
                    'type': 'new_trip_assignment'
                }
            )
            
            return True
        
        return False