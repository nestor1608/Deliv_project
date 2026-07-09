from rest_framework import permissions


class IsCustomer(permissions.BasePermission):
    """
    Permiso para verificar que el usuario es un cliente
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "customer"
