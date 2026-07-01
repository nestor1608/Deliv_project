from django.contrib import admin
from .models import Customer, CustomerAddress

class CustomerAddressInline(admin.TabularInline):
    model = CustomerAddress
    extra = 1

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'loyalty_points', 'is_premium', 'created_at')
    list_filter = ('is_premium', 'preferred_payment_method', 'created_at')
    search_fields = ('user__username', 'user__email')
    inlines = [CustomerAddressInline]

@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ('customer', 'label', 'city', 'is_default')
    list_filter = ('is_default', 'city', 'country')
    search_fields = ('customer__user__username', 'label', 'street_address')