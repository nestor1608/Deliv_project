from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "vendors"

router = DefaultRouter()
router.register(r"categories", views.VendorCategoryViewSet, basename="categories")
router.register(r"vendors", views.VendorViewSet, basename="vendors")
router.register(r"products", views.ProductViewSet, basename="products")
router.register(r"ratings", views.VendorRatingViewSet, basename="ratings")

urlpatterns = [
    path("", include(router.urls)),
]
