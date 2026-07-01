from rest_framework import permissions

class IsDeliveryPerson(permissions.BasePermission):
    """
    Permission para verificar que el usuario sea un repartidor
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            hasattr(request.user, 'delivery_profile')
        )