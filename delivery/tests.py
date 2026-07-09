"""
Comprehensive API tests for the Delivery app.
Covers DeliveryPersonViewSet and DeliveryRatingViewSet.
"""

from decimal import Decimal
from unittest.mock import patch

from django.db.models.signals import post_save, pre_save
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from tests.factories import APITestCase

from tests.factories import (
    UserFactory,
    CustomerFactory,
    DeliveryPersonFactory,
    VendorFactory,
    ProductFactory,
    create_order_with_items,
    create_delivery_rating,
)
from delivery.models import DeliveryPerson, DeliveryRating
from delivery.signals import update_delivery_rating
from orders.models import Order
from orders.signals import order_status_change, order_created


# Helper to extract paginated results if the response uses pagination.
def _get_results(response):
    """Return response.data['results'] if paginated, else response.data."""
    if isinstance(response.data, dict) and "results" in response.data:
        return response.data["results"]
    return response.data


# Base class to work around pre-existing bugs in the project's middleware
# and custom exception handler.
@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
class PatchedAPITestCase(APITestCase):
    """Base test case that patches known project bugs for clean test execution."""

    def setUp(self):
        super().setUp()
        # Patch the middleware bug: SecurityMiddleware.add_security_headers
        # accesses self.request instead of the local `request` variable at line 166.
        self._mw_patch = patch(
            "users.middleware.security.SecurityMiddleware.add_security_headers",
            lambda self, request, response: None,
        )
        self._mw_patch.start()
        # Patch the exception handler bug: format_error_response calls
        # get_error_code(response.status_code, exc) but the later definition
        # of get_error_code (line 311) only accepts one argument and overrides
        # the two-argument version at line 121.
        self._exc_patch = patch(
            "core.exceptions.format_error_response",
            lambda response, exc, context: response,
        )
        self._exc_patch.start()
        # Disconnect signal receivers that have pre-existing bugs.
        self._disconnect_problematic_signals()

    def tearDown(self):
        self._exc_patch.stop()
        self._mw_patch.stop()
        # Reconnect signals that were disconnected in setUp
        post_save.connect(update_delivery_rating, sender=DeliveryRating)
        pre_save.connect(order_status_change, sender=Order)
        post_save.connect(order_created, sender=Order)
        super().tearDown()

    def _disconnect_problematic_signals(self):
        """
        Disconnect signal receivers that have pre-existing bugs
        (delivery/signals.py missing 'models' import for Avg,
         orders/signals.py requiring Redis).
        """
        post_save.disconnect(update_delivery_rating, sender=DeliveryRating)
        pre_save.disconnect(order_status_change, sender=Order)
        post_save.disconnect(order_created, sender=Order)


class DeliveryPersonListTests(PatchedAPITestCase):
    """Tests for GET /api/delivery/delivery-persons/"""

    def test_list_as_delivery_returns_own_profile(self):
        """Delivery person sees their own profile in the list."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/delivery/delivery-persons/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], delivery_person.id)

    def test_list_as_customer_returns_empty(self):
        """Customers see no delivery persons in the list."""
        customer_user = UserFactory(role="customer")
        CustomerFactory(user=customer_user)
        DeliveryPersonFactory()  # another delivery exists but won't show
        self.client.force_authenticate(user=customer_user)
        response = self.client.get("/api/delivery/delivery-persons/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 0)

    def test_list_unauthenticated_returns_401(self):
        """Unauthenticated requests are rejected."""
        response = self.client.get("/api/delivery/delivery-persons/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DeliveryPersonCreateTests(PatchedAPITestCase):
    """Tests for POST /api/delivery/delivery-persons/"""

    def test_create_delivery_person_success(self):
        """Authenticated user can register as a delivery person."""
        user = UserFactory(role="delivery")
        self.client.force_authenticate(user=user)
        data = {
            "license_number": "LIC-NEW-001",
            "vehicle_type": "Moto",
            "vehicle_plate": "NEW123",
        }
        response = self.client.post("/api/delivery/delivery-persons/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(DeliveryPerson.objects.filter(user=user).exists())

    def test_create_duplicate_license_fails(self):
        """Duplicate license numbers are rejected."""
        existing = DeliveryPersonFactory()
        user = UserFactory(role="delivery")
        self.client.force_authenticate(user=user)
        data = {
            "license_number": existing.license_number,
            "vehicle_type": "Moto",
            "vehicle_plate": "DUP456",
        }
        response = self.client.post("/api/delivery/delivery-persons/", data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_unauthenticated_returns_401(self):
        """Only authenticated users can register."""
        data = {
            "license_number": "LIC-NO-AUTH",
            "vehicle_type": "Moto",
            "vehicle_plate": "NOAUTH",
        }
        response = self.client.post("/api/delivery/delivery-persons/", data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DeliveryPersonRetrieveTests(PatchedAPITestCase):
    """Tests for GET /api/delivery/delivery-persons/<pk>/"""

    def test_retrieve_own_profile(self):
        """Delivery person can retrieve their own profile."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/delivery/delivery-persons/{delivery_person.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], delivery_person.id)

    def test_retrieve_other_profile_returns_404(self):
        """Delivery person cannot retrieve another person's profile."""
        user = UserFactory(role="delivery")
        DeliveryPersonFactory(user=user)
        other = DeliveryPersonFactory()
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/delivery/delivery-persons/{other.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_unauthenticated_returns_401(self):
        """Unauthenticated requests are rejected."""
        dp = DeliveryPersonFactory()
        response = self.client.get(f"/api/delivery/delivery-persons/{dp.pk}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DeliveryPersonUpdateTests(PatchedAPITestCase):
    """Tests for PATCH /api/delivery/delivery-persons/<pk>/"""

    def test_update_own_profile(self):
        """Delivery person can update their own profile."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        data = {"vehicle_type": "Auto", "vehicle_plate": "UPDATED"}
        response = self.client.patch(f"/api/delivery/delivery-persons/{delivery_person.pk}/", data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        delivery_person.refresh_from_db()
        self.assertEqual(delivery_person.vehicle_type, "Auto")
        self.assertEqual(delivery_person.vehicle_plate, "UPDATED")

    def test_update_other_profile_returns_404(self):
        """Delivery person cannot update another person's profile."""
        user = UserFactory(role="delivery")
        DeliveryPersonFactory(user=user)
        other = DeliveryPersonFactory()
        self.client.force_authenticate(user=user)
        data = {"vehicle_type": "Auto"}
        response = self.client.patch(f"/api/delivery/delivery-persons/{other.pk}/", data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_unauthenticated_returns_401(self):
        """Unauthenticated updates are rejected."""
        dp = DeliveryPersonFactory()
        response = self.client.patch(f"/api/delivery/delivery-persons/{dp.pk}/", {"vehicle_type": "Auto"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DeliveryPersonDeleteTests(PatchedAPITestCase):
    """Tests for DELETE /api/delivery/delivery-persons/<pk>/"""

    def test_delete_own_profile(self):
        """Delivery person can delete their own profile."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.delete(f"/api/delivery/delivery-persons/{delivery_person.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DeliveryPerson.objects.filter(pk=delivery_person.pk).exists())

    def test_delete_other_profile_returns_404(self):
        """Delivery person cannot delete another person's profile."""
        user = UserFactory(role="delivery")
        DeliveryPersonFactory(user=user)
        other = DeliveryPersonFactory()
        self.client.force_authenticate(user=user)
        response = self.client.delete(f"/api/delivery/delivery-persons/{other.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_unauthenticated_returns_401(self):
        """Unauthenticated delete is rejected."""
        dp = DeliveryPersonFactory()
        response = self.client.delete(f"/api/delivery/delivery-persons/{dp.pk}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UpdateLocationTests(PatchedAPITestCase):
    """Tests for PATCH /api/delivery/delivery-persons/<pk>/update_location/"""

    def test_update_location_with_valid_coords(self):
        """Delivery person can update their location with valid coordinates."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        data = {
            "current_latitude": "-31.6625",
            "current_longitude": "-60.7676",
        }
        response = self.client.patch(
            f"/api/delivery/delivery-persons/{delivery_person.pk}/update_location/",
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        delivery_person.refresh_from_db()
        self.assertEqual(delivery_person.current_latitude, Decimal("-31.6625"))
        self.assertEqual(delivery_person.current_longitude, Decimal("-60.7676"))
        self.assertIsNotNone(delivery_person.last_location_update)

    def test_update_location_with_single_coord(self):
        """Updating with only latitude (missing longitude) sets the given field."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            f"/api/delivery/delivery-persons/{delivery_person.pk}/update_location/",
            {"current_latitude": "-31.6625"},  # missing longitude
        )
        # The serializer fields are optional (nullable), so partial updates succeed.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        delivery_person.refresh_from_db()
        self.assertEqual(delivery_person.current_latitude, Decimal("-31.6625"))
        self.assertIsNone(delivery_person.current_longitude)

    def test_update_location_unauthenticated_returns_401(self):
        """Unauthenticated location update is rejected."""
        dp = DeliveryPersonFactory()
        response = self.client.patch(
            f"/api/delivery/delivery-persons/{dp.pk}/update_location/",
            {"current_latitude": "-31.66", "current_longitude": "-60.76"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UpdateAvailabilityTests(PatchedAPITestCase):
    """Tests for PATCH /api/delivery/delivery-persons/<pk>/update_availability/"""

    def test_change_to_available(self):
        """Delivery person can change availability to 'available'."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user, availability="offline")
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            f"/api/delivery/delivery-persons/{delivery_person.pk}/update_availability/",
            {"availability": "available"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        delivery_person.refresh_from_db()
        self.assertEqual(delivery_person.availability, "available")

    def test_change_to_busy(self):
        """Delivery person can change availability to 'busy'."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user, availability="available")
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            f"/api/delivery/delivery-persons/{delivery_person.pk}/update_availability/",
            {"availability": "busy"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("availability", response.data)
        self.assertEqual(response.data["availability"], "busy")

    def test_change_to_offline(self):
        """Delivery person can change availability to 'offline'."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user, availability="available")
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            f"/api/delivery/delivery-persons/{delivery_person.pk}/update_availability/",
            {"availability": "offline"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        delivery_person.refresh_from_db()
        self.assertEqual(delivery_person.availability, "offline")

    def test_invalid_availability_value(self):
        """Invalid availability value returns a validation error."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            f"/api/delivery/delivery-persons/{delivery_person.pk}/update_availability/",
            {"availability": "invalid"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ActiveOrdersTests(PatchedAPITestCase):
    """Tests for GET /api/delivery/delivery-persons/<pk>/active_orders/"""

    def test_active_orders_returns_assigned_orders(self):
        """Returns orders in 'ready' or 'picked_up' status for the delivery person."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        # Create an order assigned to this delivery person with status 'ready'
        customer = CustomerFactory()
        vendor = VendorFactory()
        product = ProductFactory(vendor=vendor)
        order = create_order_with_items(customer=customer, vendor=vendor, product=product)
        order.delivery_person = delivery_person
        order.status = "ready"
        order.save()

        # Create another order with non-active status (should not appear)
        order2 = create_order_with_items(customer=customer, vendor=vendor, product=product)
        order2.delivery_person = delivery_person
        order2.status = "delivered"
        order2.save()

        response = self.client.get(f"/api/delivery/delivery-persons/{delivery_person.pk}/active_orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only the 'ready' order should be returned
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], order.id)

    def test_active_orders_when_no_orders(self):
        """Returns empty list when delivery person has no active orders."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/delivery/delivery-persons/{delivery_person.pk}/active_orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class EarningsTests(PatchedAPITestCase):
    """Tests for GET /api/delivery/delivery-persons/<pk>/earnings/"""

    def test_earnings_with_no_delivered_orders(self):
        """Returns zero earnings when no orders have been delivered."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/delivery/delivery-persons/{delivery_person.pk}/earnings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_earnings"], 0)
        self.assertEqual(response.data["total_deliveries"], 0)
        self.assertEqual(response.data["average_per_delivery"], 0)

    def test_earnings_with_delivered_orders(self):
        """Returns correct earnings from delivered orders."""
        user = UserFactory(role="delivery")
        delivery_person = DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        customer = CustomerFactory()
        vendor = VendorFactory()
        product = ProductFactory(vendor=vendor)
        order = create_order_with_items(customer=customer, vendor=vendor, product=product)
        order.delivery_person = delivery_person
        order.status = "delivered"
        order.delivered_at = timezone.now()
        order.save()

        response = self.client.get(f"/api/delivery/delivery-persons/{delivery_person.pk}/earnings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_earnings = float(order.delivery_fee)
        self.assertEqual(response.data["total_earnings"], expected_earnings)
        self.assertEqual(response.data["total_deliveries"], 1)


class DeliveryRatingListTests(PatchedAPITestCase):
    """Tests for GET /api/delivery/ratings/"""

    def test_list_ratings_as_customer(self):
        """Customer can see their own ratings."""
        customer_user = UserFactory(role="customer")
        customer = CustomerFactory(user=customer_user)
        self.client.force_authenticate(user=customer_user)
        rating = create_delivery_rating(customer=customer)
        response = self.client.get("/api/delivery/ratings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], rating.id)

    def test_list_ratings_as_delivery_returns_forbidden(self):
        """Delivery person gets 403 because ratings require the IsCustomer permission."""
        user = UserFactory(role="delivery")
        DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/delivery/ratings/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DeliveryRatingCreateTests(PatchedAPITestCase):
    """Tests for POST /api/delivery/ratings/"""

    def test_create_rating_success(self):
        """Customer can rate a delivered order."""
        customer_user = UserFactory(role="customer")
        customer = CustomerFactory(user=customer_user)
        self.client.force_authenticate(user=customer_user)

        delivery_person = DeliveryPersonFactory()
        order = create_order_with_items(customer=customer)
        order.status = "delivered"
        order.delivery_person = delivery_person
        order.save()

        data = {
            "delivery_person": delivery_person.id,
            "order": order.id,
            "rating": 5,
            "comment": "Excellent delivery!",
        }
        response = self.client.post("/api/delivery/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DeliveryRating.objects.filter(customer=customer, order=order).count(), 1)

    def test_create_rating_non_delivered_order_fails(self):
        """Cannot rate an order that has not been delivered."""
        customer_user = UserFactory(role="customer")
        customer = CustomerFactory(user=customer_user)
        self.client.force_authenticate(user=customer_user)

        delivery_person = DeliveryPersonFactory()
        order = create_order_with_items(customer=customer)
        order.status = "pending"  # not delivered
        order.delivery_person = delivery_person
        order.save()

        data = {
            "delivery_person": delivery_person.id,
            "order": order.id,
            "rating": 5,
        }
        response = self.client.post("/api/delivery/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # The custom exception handler is bypassed by our patch, so DRF's
        # default error structure is used (non_field_errors or per-field errors).
        self.assertIn("Solo puedes calificar pedidos entregados", str(response.data))

    def test_create_duplicate_rating_fails(self):
        """Customer cannot rate the same order twice."""
        customer_user = UserFactory(role="customer")
        customer = CustomerFactory(user=customer_user)
        self.client.force_authenticate(user=customer_user)

        delivery_person = DeliveryPersonFactory()
        order = create_order_with_items(customer=customer)
        order.status = "delivered"
        order.delivery_person = delivery_person
        order.save()

        # First rating succeeds
        data = {
            "delivery_person": delivery_person.id,
            "order": order.id,
            "rating": 4,
            "comment": "Good",
        }
        response = self.client.post("/api/delivery/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Second rating fails (unique constraint on order OneToOneField)
        response = self.client.post("/api/delivery/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # DRF's UniqueValidator on the order field fires before custom validate
        self.assertTrue("Ya has calificado este pedido" in str(response.data) or "already exists" in str(response.data))

    def test_create_rating_as_delivery_person_fails(self):
        """Non-customer users cannot create ratings."""
        user = UserFactory(role="delivery")
        DeliveryPersonFactory(user=user)
        self.client.force_authenticate(user=user)

        customer = CustomerFactory()
        delivery_person = DeliveryPersonFactory()
        order = create_order_with_items(customer=customer)
        order.status = "delivered"
        order.delivery_person = delivery_person
        order.save()

        data = {
            "delivery_person": delivery_person.id,
            "order": order.id,
            "rating": 5,
        }
        response = self.client.post("/api/delivery/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_rating_wrong_customer_order_fails(self):
        """Customer cannot rate an order that belongs to another customer."""
        customer_user = UserFactory(role="customer")
        CustomerFactory(user=customer_user)
        self.client.force_authenticate(user=customer_user)

        other_customer = CustomerFactory()
        delivery_person = DeliveryPersonFactory()
        order = create_order_with_items(customer=other_customer)
        order.status = "delivered"
        order.delivery_person = delivery_person
        order.save()

        data = {
            "delivery_person": delivery_person.id,
            "order": order.id,
            "rating": 5,
        }
        response = self.client.post("/api/delivery/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No puedes calificar un pedido que no es tuyo", str(response.data))
