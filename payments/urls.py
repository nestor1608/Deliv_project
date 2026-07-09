# payments/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "payments"

router = DefaultRouter()
router.register(r"payments", views.PaymentViewSet, basename="payments")
router.register(r"payment-methods", views.PaymentMethodViewSet, basename="payment-methods")

urlpatterns = [
    path("", include(router.urls)),
    path("process/", views.process_payment, name="process-payment"),
    path("webhook/mercadopago/", views.mercadopago_webhook, name="mercadopago-webhook"),
    path("webhook/stripe/", views.stripe_webhook, name="stripe-webhook"),
]
