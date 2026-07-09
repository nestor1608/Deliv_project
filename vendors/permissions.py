from rest_framework import permissions


class IsVendor(permissions.BasePermission):
    """
    Permiso para verificar que el usuario es un comercio
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "vendor"


class IsVendorOwner(permissions.BasePermission):
    """
    Permiso para verificar que el usuario es dueño del comercio
    """

    def has_object_permission(self, request, view, obj):
        # Para el modelo Vendor
        if hasattr(obj, "user"):
            return obj.user == request.user
        # Para productos del vendor
        elif hasattr(obj, "vendor"):
            return obj.vendor.user == request.user
        return False
