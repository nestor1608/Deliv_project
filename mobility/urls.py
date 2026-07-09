from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "mobility"

router = DefaultRouter()
router.register(r"drivers", views.DriverViewSet, basename="drivers")
router.register(r"trips", views.TripViewSet, basename="trips")
router.register(r"ratings", views.TripRatingViewSet, basename="ratings")

urlpatterns = [
    path("", include(router.urls)),
    path("estimate/", views.trip_estimate, name="trip-estimate"),
    path("nearby-drivers/", views.nearby_drivers, name="nearby-drivers"),
]
