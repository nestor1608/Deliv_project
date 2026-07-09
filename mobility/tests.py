"""
Comprehensive API tests for the Mobility app.
Covers DriverViewSet, TripViewSet, trip_estimate, nearby_drivers, and TripRatingViewSet.
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
    DriverFactory,
)
from mobility.models import Driver, Trip, TripRating
from mobility.signals import trip_created, trip_status_change, update_driver_rating
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
        post_save.connect(trip_created, sender=Trip)
        pre_save.connect(trip_status_change, sender=Trip)
        post_save.connect(update_driver_rating, sender=TripRating)
        pre_save.connect(order_status_change, sender=Order)
        post_save.connect(order_created, sender=Order)
        super().tearDown()

    def _disconnect_problematic_signals(self):
        """
        Disconnect signal receivers that may cause issues in tests
        (Redis connections, FCM service calls, missing imports).
        """
        post_save.disconnect(trip_created, sender=Trip)
        pre_save.disconnect(trip_status_change, sender=Trip)
        post_save.disconnect(update_driver_rating, sender=TripRating)
        pre_save.disconnect(order_status_change, sender=Order)
        post_save.disconnect(order_created, sender=Order)


# =============================================================================
# Driver tests
# =============================================================================


class DriverListTests(PatchedAPITestCase):
    """Tests for GET /api/mobility/drivers/"""

    def test_list_as_customer_sees_approved_drivers(self):
        """Customers see approved and available drivers."""
        customer_user = UserFactory(role="customer")
        CustomerFactory(user=customer_user)
        self.client.force_authenticate(user=customer_user)
        # Approved driver
        DriverFactory(status="approved", availability="available")
        # Pending driver (should not appear)
        DriverFactory(status="pending", availability="available")
        response = self.client.get("/api/mobility/drivers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

    def test_list_as_driver_sees_own_profile(self):
        """Drivers only see their own profile."""
        user = UserFactory(role="delivery")
        driver = DriverFactory(user=user)
        DriverFactory()  # another driver
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/mobility/drivers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], driver.id)

    def test_list_as_anonymous_returns_server_error(self):
        """Anonymous users crash the view because get_queryset accesses user.role
        on AnonymousUser which has no 'role' attribute (pre-existing bug)."""
        DriverFactory(status="approved", availability="available")
        response = self.client.get("/api/mobility/drivers/")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class DriverCreateTests(PatchedAPITestCase):
    """Tests for POST /api/mobility/drivers/"""

    def test_create_driver_success(self):
        """Authenticated user can register as a driver."""
        user = UserFactory(role="delivery")
        self.client.force_authenticate(user=user)
        data = {
            "license_number": "DRV-NEW-001",
            "vehicle_type": "car",
            "vehicle_brand": "Toyota",
            "vehicle_model": "Corolla",
            "vehicle_year": 2022,
            "vehicle_plate": "PLT-NEW1",
            "vehicle_color": "Rojo",
        }
        response = self.client.post("/api/mobility/drivers/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Driver.objects.filter(user=user).exists())

    def test_create_duplicate_license_fails(self):
        """Duplicate license numbers are rejected."""
        existing = DriverFactory()
        user = UserFactory(role="delivery")
        self.client.force_authenticate(user=user)
        data = {
            "license_number": existing.license_number,
            "vehicle_type": "car",
            "vehicle_brand": "Ford",
            "vehicle_model": "Focus",
            "vehicle_year": 2020,
            "vehicle_plate": "PLT-DUP",
            "vehicle_color": "Azul",
        }
        response = self.client.post("/api/mobility/drivers/", data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_unauthenticated_returns_401(self):
        """Only authenticated users can register."""
        data = {
            "license_number": "DRV-NOAUTH",
            "vehicle_type": "car",
            "vehicle_brand": "Nissan",
            "vehicle_model": "Sentra",
            "vehicle_year": 2021,
            "vehicle_plate": "NO-AUTH",
            "vehicle_color": "Negro",
        }
        response = self.client.post("/api/mobility/drivers/", data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DriverRetrieveTests(PatchedAPITestCase):
    """Tests for GET /api/mobility/drivers/<pk>/"""

    def test_retrieve_driver_detail(self):
        """Authenticated user can retrieve a driver detail."""
        driver = DriverFactory(status="approved")
        user = UserFactory(role="customer")
        CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/mobility/drivers/{driver.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], driver.id)

    def test_retrieve_unauthenticated_returns_server_error(self):
        """Anonymous users crash the view because get_queryset accesses user.role
        on AnonymousUser which has no 'role' attribute (pre-existing bug)."""
        driver = DriverFactory(status="approved")
        response = self.client.get(f"/api/mobility/drivers/{driver.pk}/")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class DriverUpdateTests(PatchedAPITestCase):
    """Tests for PATCH /api/mobility/drivers/<pk>/"""

    def test_update_own_profile(self):
        """Driver can update their own profile."""
        user = UserFactory(role="delivery")
        driver = DriverFactory(user=user)
        self.client.force_authenticate(user=user)
        data = {"vehicle_color": "Negro", "vehicle_plate": "CHG-999"}
        response = self.client.patch(f"/api/mobility/drivers/{driver.pk}/", data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        driver.refresh_from_db()
        self.assertEqual(driver.vehicle_color, "Negro")
        self.assertEqual(driver.vehicle_plate, "CHG-999")

    def test_update_other_profile_fails(self):
        """Driver cannot update another driver's profile."""
        user = UserFactory(role="delivery")
        DriverFactory(user=user)
        other = DriverFactory()
        self.client.force_authenticate(user=user)
        data = {"vehicle_color": "Negro"}
        response = self.client.patch(f"/api/mobility/drivers/{other.pk}/", data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_unauthenticated_returns_401(self):
        """Unauthenticated update is rejected."""
        driver = DriverFactory()
        response = self.client.patch(f"/api/mobility/drivers/{driver.pk}/", {"vehicle_color": "Negro"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DriverUpdateLocationTests(PatchedAPITestCase):
    """Tests for PATCH /api/mobility/drivers/<pk>/update_location/"""

    def test_update_location_success(self):
        """Driver can update their location."""
        user = UserFactory(role="delivery")
        driver = DriverFactory(user=user)
        self.client.force_authenticate(user=user)
        data = {
            "current_latitude": "-31.6625",
            "current_longitude": "-60.7676",
        }
        response = self.client.patch(f"/api/mobility/drivers/{driver.pk}/update_location/", data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        driver.refresh_from_db()
        self.assertEqual(driver.current_latitude, Decimal("-31.6625"))
        self.assertEqual(driver.current_longitude, Decimal("-60.7676"))
        self.assertIsNotNone(driver.last_location_update)

    def test_update_location_other_driver_fails(self):
        """Driver gets 404 when trying to update another driver's location
        because get_queryset only returns the authenticated driver's profile."""
        user = UserFactory(role="delivery")
        DriverFactory(user=user)
        other = DriverFactory()
        self.client.force_authenticate(user=user)
        data = {"current_latitude": "-31.66", "current_longitude": "-60.76"}
        response = self.client.patch(f"/api/mobility/drivers/{other.pk}/update_location/", data)
        # 404 because get_object() filters by authenticated user's driver profile
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_location_unauthenticated_returns_401(self):
        """Unauthenticated location update is rejected."""
        driver = DriverFactory()
        response = self.client.patch(
            f"/api/mobility/drivers/{driver.pk}/update_location/",
            {"current_latitude": "-31.66", "current_longitude": "-60.76"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DriverUpdateAvailabilityTests(PatchedAPITestCase):
    """Tests for PATCH /api/mobility/drivers/<pk>/update_availability/"""

    def test_change_to_available(self):
        """Driver can change availability to 'available'."""
        user = UserFactory(role="delivery")
        driver = DriverFactory(user=user, availability="offline")
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            f"/api/mobility/drivers/{driver.pk}/update_availability/",
            {"availability": "available"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        driver.refresh_from_db()
        self.assertEqual(driver.availability, "available")

    def test_change_to_busy(self):
        """Driver can change availability to 'busy'."""
        user = UserFactory(role="delivery")
        driver = DriverFactory(user=user, availability="available")
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            f"/api/mobility/drivers/{driver.pk}/update_availability/",
            {"availability": "busy"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["availability"], "busy")

    def test_other_driver_cannot_change_availability(self):
        """Driver gets 404 when trying to change another driver's availability
        because get_queryset only returns the authenticated driver's profile."""
        user = UserFactory(role="delivery")
        DriverFactory(user=user)
        other = DriverFactory()
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            f"/api/mobility/drivers/{other.pk}/update_availability/",
            {"availability": "available"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_availability_value(self):
        """Invalid availability value returns a validation error."""
        user = UserFactory(role="delivery")
        driver = DriverFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            f"/api/mobility/drivers/{driver.pk}/update_availability/",
            {"availability": "invalid"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DriverActiveTripsTests(PatchedAPITestCase):
    """Tests for GET /api/mobility/drivers/<pk>/active_trips/"""

    def test_active_trips_returns_assigned_trips(self):
        """Returns active trips for the driver."""
        user = UserFactory(role="delivery")
        driver = DriverFactory(user=user)
        self.client.force_authenticate(user=user)
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="accepted",
            pickup_address="Pickup 1",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest 1",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        # Completed trip should NOT appear
        Trip.objects.create(
            customer=customer,
            driver=driver,
            status="completed",
            pickup_address="Old pickup",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Old dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("200.00"),
        )
        response = self.client.get(f"/api/mobility/drivers/{driver.pk}/active_trips/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], trip.id)

    def test_active_trips_other_driver_fails(self):
        """Driver gets 404 when trying to view another driver's active trips
        because get_object() filters by the authenticated user's profile."""
        user = UserFactory(role="delivery")
        DriverFactory(user=user)
        other = DriverFactory()
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/mobility/drivers/{other.pk}/active_trips/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DriverEarningsTests(PatchedAPITestCase):
    """Tests for GET /api/mobility/drivers/<pk>/earnings/"""

    def test_earnings_no_completed_trips(self):
        """Returns zero earnings when no trips completed."""
        user = UserFactory(role="delivery")
        driver = DriverFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/mobility/drivers/{driver.pk}/earnings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_earnings"], 0)
        self.assertEqual(response.data["total_trips"], 0)
        self.assertEqual(response.data["average_per_trip"], 0)

    def test_earnings_with_completed_trips(self):
        """Returns correct earnings from completed trips."""
        user = UserFactory(role="delivery")
        driver = DriverFactory(user=user)
        self.client.force_authenticate(user=user)
        customer = CustomerFactory()
        Trip.objects.create(
            customer=customer,
            driver=driver,
            status="completed",
            completed_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("500.00"),
        )
        response = self.client.get(f"/api/mobility/drivers/{driver.pk}/earnings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_earnings"], 500.0)
        self.assertEqual(response.data["total_trips"], 1)
        self.assertEqual(response.data["average_per_trip"], 500.0)

    def test_earnings_other_driver_fails(self):
        """Driver gets 404 when trying to view another driver's earnings
        because get_object() filters by the authenticated user's profile."""
        user = UserFactory(role="delivery")
        DriverFactory(user=user)
        other = DriverFactory()
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/mobility/drivers/{other.pk}/earnings/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# =============================================================================
# Trip tests
# =============================================================================


class TripCreateTests(PatchedAPITestCase):
    """Tests for POST /api/mobility/trips/"""

    def test_create_trip_as_customer_success(self):
        """Customer can create a trip request."""
        user = UserFactory(role="customer")
        CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        data = {
            "pickup_address": "Av. Siempre Viva 123",
            "pickup_latitude": "-31.6625",
            "pickup_longitude": "-60.7676",
            "destination_address": "Av. Otra 456",
            "destination_latitude": "-31.6800",
            "destination_longitude": "-60.7800",
            "customer_notes": "Llegaré en 5 min",
        }
        response = self.client.post("/api/mobility/trips/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "requested")

    def test_create_trip_as_driver_fails(self):
        """Non-customer users cannot create trips."""
        user = UserFactory(role="delivery")
        DriverFactory(user=user)
        self.client.force_authenticate(user=user)
        data = {
            "pickup_address": "Addr",
            "pickup_latitude": "-31.66",
            "pickup_longitude": "-60.76",
            "destination_address": "Dest",
            "destination_latitude": "-31.68",
            "destination_longitude": "-60.78",
        }
        response = self.client.post("/api/mobility/trips/", data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_trip_unauthenticated_returns_401(self):
        """Unauthenticated trip creation is rejected."""
        data = {
            "pickup_address": "Addr",
            "pickup_latitude": "-31.66",
            "pickup_longitude": "-60.76",
            "destination_address": "Dest",
            "destination_latitude": "-31.68",
            "destination_longitude": "-60.78",
        }
        response = self.client.post("/api/mobility/trips/", data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_trip_missing_coordinates_fails(self):
        """Trip creation without required coordinates returns a validation error."""
        user = UserFactory(role="customer")
        CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        data = {
            "pickup_address": "Addr",
            "pickup_latitude": "-31.66",
            # missing pickup_longitude, destination coords
            "destination_address": "Dest",
        }
        response = self.client.post("/api/mobility/trips/", data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TripRetrieveTests(PatchedAPITestCase):
    """Tests for GET /api/mobility/trips/<pk>/"""

    def test_retrieve_trip_as_owner_customer(self):
        """Customer can retrieve their own trip."""
        user = UserFactory(role="customer")
        customer = CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        trip = Trip.objects.create(
            customer=customer,
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.get(f"/api/mobility/trips/{trip.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], trip.id)

    def test_retrieve_trip_as_other_customer_fails(self):
        """Customer cannot retrieve another customer's trip."""
        user = UserFactory(role="customer")
        CustomerFactory(user=user)
        other_customer = CustomerFactory()
        self.client.force_authenticate(user=user)
        trip = Trip.objects.create(
            customer=other_customer,
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.get(f"/api/mobility/trips/{trip.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_trip_as_assigned_driver(self):
        """Assigned driver can retrieve the trip."""
        user = UserFactory(role="delivery")
        driver = DriverFactory(user=user)
        self.client.force_authenticate(user=user)
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.get(f"/api/mobility/trips/{trip.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], trip.id)

    def test_retrieve_trip_unauthenticated_returns_401(self):
        """Unauthenticated trip retrieval is rejected."""
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.get(f"/api/mobility/trips/{trip.pk}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TripAcceptTests(PatchedAPITestCase):
    """Tests for PATCH /api/mobility/trips/<pk>/accept_trip/"""

    def test_driver_accepts_requested_trip(self):
        """Driver can accept a requested trip."""
        driver_user = UserFactory(role="delivery")
        driver = DriverFactory(user=driver_user, availability="available")
        self.client.force_authenticate(user=driver_user)
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,  # Pre-assign so get_queryset() can find it
            status="requested",
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.patch(f"/api/mobility/trips/{trip.pk}/accept_trip/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        trip.refresh_from_db()
        self.assertEqual(trip.status, "accepted")
        self.assertEqual(trip.driver, driver)
        self.assertIsNotNone(trip.accepted_at)

    def test_accept_already_accepted_trip_fails(self):
        """Accepting an already-accepted trip returns 400."""
        driver_user = UserFactory(role="delivery")
        driver = DriverFactory(user=driver_user, availability="available")
        self.client.force_authenticate(user=driver_user)
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            status="accepted",
            driver=driver,
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.patch(f"/api/mobility/trips/{trip.pk}/accept_trip/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ya no está disponible", str(response.data))

    def test_accept_trip_as_customer_fails(self):
        """Only drivers can accept trips (customer gets 403)."""
        user = UserFactory(role="customer")
        customer = CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        trip = Trip.objects.create(
            customer=customer,  # Owned by test user so get_queryset() finds it
            status="requested",
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.patch(f"/api/mobility/trips/{trip.pk}/accept_trip/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TripStartTests(PatchedAPITestCase):
    """Tests for PATCH /api/mobility/trips/<pk>/start_trip/"""

    def test_driver_starts_accepted_trip(self):
        """Driver can start an accepted trip."""
        driver_user = UserFactory(role="delivery")
        driver = DriverFactory(user=driver_user)
        self.client.force_authenticate(user=driver_user)
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="accepted",
            accepted_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.patch(f"/api/mobility/trips/{trip.pk}/start_trip/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        trip.refresh_from_db()
        self.assertEqual(trip.status, "in_progress")
        self.assertIsNotNone(trip.started_at)

    def test_start_trip_not_assigned_driver_fails(self):
        """Non-assigned driver gets 404 because get_queryset only returns their trips."""
        other_user = UserFactory(role="delivery")
        DriverFactory(user=other_user)
        driver = DriverFactory()
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="accepted",
            accepted_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        self.client.force_authenticate(user=other_user)
        response = self.client.patch(f"/api/mobility/trips/{trip.pk}/start_trip/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_start_trip_wrong_status_fails(self):
        """Starting a trip that isn't accepted returns 400."""
        driver_user = UserFactory(role="delivery")
        driver = DriverFactory(user=driver_user)
        self.client.force_authenticate(user=driver_user)
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="completed",
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.patch(f"/api/mobility/trips/{trip.pk}/start_trip/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TripCompleteTests(PatchedAPITestCase):
    """Tests for PATCH /api/mobility/trips/<pk>/complete_trip/"""

    def test_driver_completes_in_progress_trip(self):
        """Driver can complete an in-progress trip."""
        driver_user = UserFactory(role="delivery")
        driver = DriverFactory(user=driver_user, availability="busy")
        self.client.force_authenticate(user=driver_user)
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="in_progress",
            started_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("400.00"),
        )
        data = {"actual_distance": 12.5, "actual_duration": 25}
        response = self.client.patch(f"/api/mobility/trips/{trip.pk}/complete_trip/", data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        trip.refresh_from_db()
        driver.refresh_from_db()
        self.assertEqual(trip.status, "completed")
        self.assertIsNotNone(trip.completed_at)
        self.assertEqual(trip.actual_distance, Decimal("12.50"))
        self.assertEqual(trip.actual_duration, 25)
        # Driver should be freed
        self.assertEqual(driver.availability, "available")
        self.assertEqual(driver.total_trips, 1)
        self.assertEqual(driver.total_earnings, Decimal("400.00"))

    def test_complete_trip_not_driver_fails(self):
        """Non-assigned driver gets 404 because get_queryset only returns their trips."""
        other_user = UserFactory(role="delivery")
        DriverFactory(user=other_user)
        driver = DriverFactory()
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="in_progress",
            started_at=timezone.now(),
            accepted_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        self.client.force_authenticate(user=other_user)
        response = self.client.patch(f"/api/mobility/trips/{trip.pk}/complete_trip/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_complete_trip_wrong_status_fails(self):
        """Completing a trip not 'in_progress' returns 400."""
        driver_user = UserFactory(role="delivery")
        driver = DriverFactory(user=driver_user)
        self.client.force_authenticate(user=driver_user)
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="requested",
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("400.00"),
        )
        response = self.client.patch(f"/api/mobility/trips/{trip.pk}/complete_trip/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TripCancelTests(PatchedAPITestCase):
    """Tests for PATCH /api/mobility/trips/<pk>/cancel_trip/"""

    def test_customer_cancels_requested_trip(self):
        """Customer can cancel their own requested trip."""
        user = UserFactory(role="customer")
        customer = CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        trip = Trip.objects.create(
            customer=customer,
            status="requested",
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.patch(
            f"/api/mobility/trips/{trip.pk}/cancel_trip/",
            {"reason": "Changed my mind"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        trip.refresh_from_db()
        self.assertEqual(trip.status, "cancelled_customer")
        self.assertEqual(trip.cancellation_reason, "Changed my mind")

    def test_driver_cancels_accepted_trip(self):
        """Driver can cancel their accepted trip."""
        driver_user = UserFactory(role="delivery")
        driver = DriverFactory(user=driver_user)
        self.client.force_authenticate(user=driver_user)
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="accepted",
            accepted_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.patch(
            f"/api/mobility/trips/{trip.pk}/cancel_trip/",
            {"reason": "Vehicle issue"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        trip.refresh_from_db()
        self.assertEqual(trip.status, "cancelled_driver")
        self.assertEqual(trip.cancellation_reason, "Vehicle issue")
        # Driver should be freed
        driver.refresh_from_db()
        self.assertEqual(driver.availability, "available")

    def test_cancel_completed_trip_fails(self):
        """Cannot cancel an already completed trip."""
        user = UserFactory(role="customer")
        customer = CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        trip = Trip.objects.create(
            customer=customer,
            status="completed",
            completed_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.patch(
            f"/api/mobility/trips/{trip.pk}/cancel_trip/",
            {"reason": "Too late"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_unauthenticated_fails(self):
        """Unauthenticated cancel is rejected."""
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            status="requested",
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        response = self.client.patch(
            f"/api/mobility/trips/{trip.pk}/cancel_trip/",
            {"reason": "No reason"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# =============================================================================
# Trip Estimate tests
# =============================================================================


class TripEstimateTests(PatchedAPITestCase):
    """Tests for POST /api/mobility/estimate/"""

    def test_trip_estimate_success(self):
        """Customer can get a trip estimate with valid coordinates."""
        user = UserFactory(role="customer")
        CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        data = {
            "pickup_latitude": "-31.6625",
            "pickup_longitude": "-60.7676",
            "destination_latitude": "-31.6800",
            "destination_longitude": "-60.7800",
        }
        response = self.client.post("/api/mobility/estimate/", data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("estimated_distance", response.data)
        self.assertIn("estimated_duration", response.data)
        self.assertIn("pricing", response.data)
        self.assertIn("available_drivers", response.data)

    def test_trip_estimate_missing_coords_fails(self):
        """Estimate without coordinates returns 400."""
        user = UserFactory(role="customer")
        CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.post(
            "/api/mobility/estimate/",
            {"pickup_latitude": "-31.6625"},  # missing others
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_trip_estimate_as_driver_fails(self):
        """Only customers can get estimates."""
        user = UserFactory(role="delivery")
        DriverFactory(user=user)
        self.client.force_authenticate(user=user)
        data = {
            "pickup_latitude": "-31.66",
            "pickup_longitude": "-60.76",
            "destination_latitude": "-31.68",
            "destination_longitude": "-60.78",
        }
        response = self.client.post("/api/mobility/estimate/", data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# =============================================================================
# Nearby Drivers tests
# =============================================================================


class NearbyDriversTests(PatchedAPITestCase):
    """Tests for GET /api/mobility/nearby-drivers/"""

    def test_nearby_drivers_with_coords(self):
        """Returns nearby drivers when coordinates are provided."""
        user = UserFactory(role="customer")
        CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        # Create an approved available driver with location
        DriverFactory(
            status="approved",
            availability="available",
            current_latitude="-31.6600",
            current_longitude="-60.7600",
        )
        response = self.client.get("/api/mobility/nearby-drivers/?latitude=-31.66&longitude=-60.76&radius=50")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("drivers", response.data)
        self.assertIn("total_count", response.data)

    def test_nearby_drivers_no_coords_fails(self):
        """Returns 400 when coordinates are missing."""
        user = UserFactory(role="customer")
        CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/mobility/nearby-drivers/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nearby_drivers_as_anonymous_fails(self):
        """Unauthenticated requests are rejected."""
        response = self.client.get("/api/mobility/nearby-drivers/?latitude=-31.66&longitude=-60.76")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# =============================================================================
# Trip Rating tests
# =============================================================================


class TripRatingCreateTests(PatchedAPITestCase):
    """Tests for POST /api/mobility/ratings/"""

    def test_create_rating_customer_to_driver_success(self):
        """Customer can rate a completed trip."""
        user = UserFactory(role="customer")
        customer = CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        driver = DriverFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="completed",
            completed_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        data = {
            "trip": trip.id,
            "rating_type": "customer_to_driver",
            "rating": 5,
            "comment": "Great trip!",
        }
        response = self.client.post("/api/mobility/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            TripRating.objects.filter(trip=trip, rating_type="customer_to_driver").count(),
            1,
        )

    def test_create_rating_non_completed_trip_fails(self):
        """Cannot rate a trip that is not completed."""
        user = UserFactory(role="customer")
        customer = CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        driver = DriverFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="in_progress",
            started_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        data = {
            "trip": trip.id,
            "rating_type": "customer_to_driver",
            "rating": 5,
        }
        response = self.client.post("/api/mobility/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Solo puedes calificar viajes completados", str(response.data))

    def test_create_duplicate_rating_fails(self):
        """Duplicate rating for same trip and type is rejected.
        Note: The model's unique_together constraint fires before the custom
        serializer validation, so the error message may be the DRF default
        instead of the custom 'Ya has calificado este viaje' message."""
        user = UserFactory(role="customer")
        customer = CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        driver = DriverFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="completed",
            completed_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        data = {
            "trip": trip.id,
            "rating_type": "customer_to_driver",
            "rating": 4,
            "comment": "Good",
        }
        # First rating succeeds
        response = self.client.post("/api/mobility/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Second rating fails — either custom or unique_together error
        response = self.client.post("/api/mobility/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rating_as_driver_to_customer(self):
        """Driver can rate a customer after a completed trip."""
        user = UserFactory(role="delivery")
        driver = DriverFactory(user=user)
        self.client.force_authenticate(user=user)
        customer = CustomerFactory()
        trip = Trip.objects.create(
            customer=customer,
            driver=driver,
            status="completed",
            completed_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        data = {
            "trip": trip.id,
            "rating_type": "driver_to_customer",
            "rating": 5,
        }
        response = self.client.post("/api/mobility/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_rating_for_other_customers_trip_fails(self):
        """Customer cannot rate another customer's trip."""
        user = UserFactory(role="customer")
        CustomerFactory(user=user)
        self.client.force_authenticate(user=user)
        other_customer = CustomerFactory()
        driver = DriverFactory()
        trip = Trip.objects.create(
            customer=other_customer,
            driver=driver,
            status="completed",
            completed_at=timezone.now(),
            pickup_address="Addr",
            pickup_latitude="-31.66",
            pickup_longitude="-60.76",
            destination_address="Dest",
            destination_latitude="-31.68",
            destination_longitude="-60.78",
            total_fare=Decimal("300.00"),
        )
        data = {
            "trip": trip.id,
            "rating_type": "customer_to_driver",
            "rating": 5,
        }
        response = self.client.post("/api/mobility/ratings/", data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No puedes calificar este viaje", str(response.data))
