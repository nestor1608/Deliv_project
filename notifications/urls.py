from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "notifications"

router = DefaultRouter()
router.register(r"notifications", views.NotificationViewSet, basename="notifications")
router.register(r"devices", views.UserDeviceViewSet, basename="devices")

urlpatterns = [
    path("", include(router.urls)),
    path("send-bulk/", views.send_bulk_notification, name="send-bulk"),
    path("mark-read/<int:notification_id>/", views.mark_as_read, name="mark-read"),
]
