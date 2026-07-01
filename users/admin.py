from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

# USERS APP - admin.py
# @admin.register(User)
# class UserAdmin(BaseUserAdmin):
#     """Configuración del admin para User"""
    
#     list_display = ('username', 'email', 'role', 'status', 'created_at')
#     list_filter = ('role', 'status', 'is_staff', 'created_at')
#     search_fields = ('username', 'email', 'phone_number')
    
#     fieldsets = BaseUserAdmin.fieldsets + (
#         ('Información adicional', {
#             'fields': ('role', 'phone_number', 'status', 'profile_picture', 
#                       'email_verified', 'phone_verified')
#         }),
#     )