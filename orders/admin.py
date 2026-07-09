from django.contrib import admin
from .models import OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("total_price",)


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ("timestamp",)


# @admin.register(Order)
# class OrderAdmin(admin.ModelAdmin):
#     list_display = ('order_number', 'customer', 'vendor', 'status', 'total_amount', 'created_at')
#     list_filter = ('status', 'payment_status', 'created_at', 'vendor')
#     search_fields = ('order_number', 'customer__user__username', 'vendor__business_name')
#     readonly_fields = ('order_number', 'created_at', 'updated_at')
#     inlines = [OrderItemInline, OrderStatusHistoryInline]

#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related(
#             'customer__user', 'vendor', 'delivery_person'
#         )
