# core/utils/order_assignment.py
from delivery.models import DeliveryPerson
from .location import calculate_distance


class OrderAssignmentService:
    """Servicio para asignar pedidos a repartidores"""

    @staticmethod
    def find_nearest_delivery_person(vendor_lat, vendor_lon, max_distance_km=10):
        """Encontrar repartidor más cercano al comercio"""
        available_delivery_persons = DeliveryPerson.objects.filter(
            status="approved", availability="available", current_latitude__isnull=False, current_longitude__isnull=False
        )

        candidates = []

        for delivery_person in available_delivery_persons:
            distance = calculate_distance(
                vendor_lat, vendor_lon, delivery_person.current_latitude, delivery_person.current_longitude
            )

            if distance <= max_distance_km:
                candidates.append(
                    {"delivery_person": delivery_person, "distance": distance, "rating": delivery_person.rating}
                )

        if not candidates:
            return None

        # Ordenar por distancia y rating (priorizar cercanía)
        candidates.sort(key=lambda x: (x["distance"], -x["rating"]))
        return candidates[0]["delivery_person"]

    @staticmethod
    def assign_order_to_delivery(order):
        """Asignar pedido a repartidor disponible"""
        delivery_person = OrderAssignmentService.find_nearest_delivery_person(
            order.vendor.latitude, order.vendor.longitude
        )

        if delivery_person:
            order.delivery_person = delivery_person
            delivery_person.availability = "busy"
            delivery_person.save()
            order.save()

            # Enviar notificación al repartidor
            from .notifications import FCMService

            fcm_service = FCMService()
            fcm_service.send_notification(
                delivery_person.user,
                "Nuevo pedido asignado",
                f"Pedido #{order.order_number} desde {order.vendor.business_name}",
                {"order_id": order.id, "order_number": order.order_number, "type": "new_delivery_assignment"},
            )

            return True

        return False
