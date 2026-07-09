from django.urls import path
from . import admin_views

urlpatterns = [
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin-dashboard'),
]
