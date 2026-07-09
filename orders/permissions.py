from rest_framework import permissions


class IsCustomer(permissions.BasePermission):
    """Permiso para usuarios con rol de cliente"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "customer"


class IsVendor(permissions.BasePermission):
    """Permiso para usuarios con rol de comercio"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "vendor"


class IsDeliveryPerson(permissions.BasePermission):
    """Permiso para usuarios con rol de repartidor"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "delivery"


class IsOrderOwner(permissions.BasePermission):
    """
    Permiso para verificar que el usuario puede ver este pedido
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        # El cliente puede ver sus pedidos
        if user.role == "customer" and hasattr(user, "customer_profile"):
            return obj.customer == user.customer_profile

        # El vendor puede ver pedidos de su comercio
        if user.role == "vendor" and hasattr(user, "vendor_profile"):
            return obj.vendor == user.vendor_profile

        # El repartidor puede ver pedidos asignados
        if user.role == "delivery":
            return obj.delivery_person == user

        return False
