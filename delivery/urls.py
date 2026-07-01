from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'delivery'

router = DefaultRouter()
router.register(r'delivery-persons', views.DeliveryPersonViewSet, basename='delivery-persons')
router.register(r'ratings', views.DeliveryRatingViewSet, basename='ratings')

urlpatterns = [
    path('', include(router.urls)),
]