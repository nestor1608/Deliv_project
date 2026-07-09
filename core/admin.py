from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from users.models import User
from vendors.models import VendorCategory, Vendor, Product
from delivery.models import DeliveryPerson
from orders.models import Order
from notifications.models import Notification


# Configuración de admin personalizada
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "status", "created_at")
    list_filter = ("role", "status", "email_verified", "phone_verified")
    search_fields = ("username", "email", "first_name", "last_name")

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Información adicional",
            {"fields": ("role", "phone_number", "status", "profile_picture", "email_verified", "phone_verified")},
        ),
    )


@admin.register(VendorCategory)
class VendorCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("business_name", "category", "status", "is_open", "rating")
    list_filter = ("category", "status", "is_open")
    search_fields = ("business_name", "user__username")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "vendor", "price", "stock", "is_available")
    list_filter = ("vendor", "category", "is_available")
    search_fields = ("name", "vendor__business_name")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer", "vendor", "status", "total_amount", "created_at")
    list_filter = ("status", "payment_status", "created_at")
    search_fields = ("order_number", "customer__user__username", "vendor__business_name")
    date_hierarchy = "created_at"


@admin.register(DeliveryPerson)
class DeliveryPersonAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "availability", "rating", "total_deliveries")
    list_filter = ("status", "availability", "vehicle_type")
    search_fields = ("user__username", "license_number")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "created_at")
    list_filter = ("status", "notification_type", "created_at")
    search_fields = ("title", "user__username")
    date_hierarchy = "created_at"
