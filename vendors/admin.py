# @admin.register(Product)
# class ProductAdmin(admin.ModelAdmin):
#     list_display = ('name', 'vendor', 'price', 'category', 'is_available')
#     list_filter = ('category', 'is_available', 'vendor')
#     search_fields = ('name', 'vendor__business_name')

# @admin.register(Vendor)
# class VendorAdmin(admin.ModelAdmin):
#     list_display = ('business_name', 'user', 'status', 'is_open')
#     list_filter = ('status', 'is_open', 'category')
#     search_fields = ('business_name', 'user__username')

#     readonly_fields = ('created_at', 'updated_at')
#     fieldsets = (
#         ('Información Básica', {
#             'fields': ('user', 'business_name', 'category', 'description')
#         }),
#         ('Información Legal', {
#             'fields': ('business_license', 'tax_id')
#         }),
#         ('Estado', {
#             'fields': ('status', 'is_open')
#         }),
#     )
