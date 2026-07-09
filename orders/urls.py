from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'orders'

router = DefaultRouter()
router.register(r'coupons', views.CouponViewSet)

urlpatterns = [
    # Pedidos del cliente
    path('', views.OrderListCreateView.as_view(), name='order-list-create'),
    path('<int:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    
    # Pedidos del comercio
    path('vendor/', views.VendorOrdersView.as_view(), name='vendor-orders'),
    path('<int:order_id>/status/', views.update_order_status, name='update-order-status'),
    
    # Seguimiento
    path('tracking/<str:order_number>/', views.order_tracking, name='order-tracking'),
    
    # Cupones
    path('validate-coupon/', views.validate_coupon, name='validate-coupon'),
    path('', include(router.urls)),
]