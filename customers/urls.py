from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    path('profile/', views.CustomerProfileView.as_view(), name='customer-profile'),
    path('addresses/', views.CustomerAddressListCreateView.as_view(), name='address-list-create'),
    path('addresses/<int:pk>/', views.CustomerAddressDetailView.as_view(), name='address-detail'),
]