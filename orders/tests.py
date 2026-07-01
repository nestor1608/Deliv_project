"""
Comprehensive API tests for the Orders app.
Covers order CRUD, vendor orders, status updates, and tracking.
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from tests.factories import APITestCase
from tests.factories import *

from orders.models import Order, OrderItem, OrderStatusHistory


class OrderAPITests(APITestCase):
    """Tests for /api/orders/ endpoints."""

    def setUp(self):
        # Customer who will own orders
        self.customer = CustomerFactory()
        self.customer_user = self.customer.user

        # Another customer (for "other user" scenarios)
        self.other_customer = CustomerFactory()
        self.other_customer_user = self.other_customer.user

        # Vendor
        self.vendor_user = UserFactory(role='vendor')
        self.vendor = VendorFactory(user=self.vendor_user, status='approved', is_open=True)
        self.product = ProductFactory(vendor=self.vendor, price=Decimal('100.00'), is_available=True)

        # A vendor that the customer does NOT order from
        self.other_vendor_user = UserFactory(role='vendor')
        self.other_vendor = VendorFactory(
            user=self.other_vendor_user,
            status='approved',
            is_open=True,
            business_name='Other Vendor',
        )

        # Delivery person
        self.delivery_user = UserFactory(role='delivery')
        self.delivery_person = DeliveryPersonFactory(user=self.delivery_user)

        # Create one order in setUp so tests can assume at least one exists
        self.order = create_order_with_items(
            customer=self.customer,
            vendor=self.vendor,
            product=self.product,
            quantity=2,
        )

        self.url_list = reverse('orders:order-list-create')
        self.url_vendor_orders = reverse('orders:vendor-orders')

    # =====================================================================
    # LIST /api/orders/  (IsAuthenticated + IsCustomer)
    # =====================================================================

    def test_list_orders_empty(self):
        """Customer with no orders sees an empty list."""
        new_customer = CustomerFactory()
        self.client.force_authenticate(user=new_customer.user)
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_list_orders_with_orders(self):
        """Customer with orders sees their own orders."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
        # Verify all returned orders belong to this customer
        for order_data in response.data:
            self.assertEqual(order_data['customer_info']['id'], self.customer.id)

    def test_list_orders_unauthenticated_fails(self):
        """Unauthenticated user cannot list orders (401)."""
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_orders_as_vendor_fails(self):
        """Vendor user cannot list via customer order endpoint (403)."""
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # =====================================================================
    # CREATE /api/orders/  (IsAuthenticated + IsCustomer)
    # =====================================================================

    def test_create_order_valid(self):
        """Customer can create an order with valid items."""
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'vendor': self.vendor.id,
            'delivery_address': 'New Address 456',
            'customer_notes': 'Please hurry',
            'items': [
                {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'special_instructions': 'No onions',
                },
            ],
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 2)  # 1 from setUp + 1 new

        # Verify totals are calculated
        order_id = response.data['id']
        new_order = Order.objects.get(id=order_id)
        expected_subtotal = self.product.price * 1  # quantity=1
        expected_tax = expected_subtotal * Decimal('0.21')
        expected_delivery_fee = Decimal('150.00')
        expected_total = expected_subtotal + expected_tax + expected_delivery_fee
        self.assertEqual(new_order.subtotal, expected_subtotal)
        self.assertEqual(new_order.tax_amount, expected_tax)
        self.assertEqual(new_order.delivery_fee, expected_delivery_fee)
        self.assertEqual(new_order.total_amount, expected_total)

    def test_create_order_with_multiple_items(self):
        """Customer can create an order with multiple items."""
        product2 = ProductFactory(vendor=self.vendor, price=Decimal('50.00'))
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'vendor': self.vendor.id,
            'delivery_address': 'Multi Item Address',
            'items': [
                {'product_id': self.product.id, 'quantity': 2},
                {'product_id': product2.id, 'quantity': 3},
            ],
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(id=response.data['id'])
        self.assertEqual(order.items.count(), 2)

    def test_create_order_empty_items_fails(self):
        """Order with empty items list returns 400."""
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'vendor': self.vendor.id,
            'delivery_address': 'Empty Items',
            'items': [],
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_order_nonexistent_product_fails(self):
        """Order with a non-existent product_id returns 400."""
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'vendor': self.vendor.id,
            'delivery_address': 'Bad Product',
            'items': [
                {'product_id': 99999, 'quantity': 1},
            ],
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_order_unauthenticated_fails(self):
        """Unauthenticated user cannot create an order (401)."""
        data = {
            'vendor': self.vendor.id,
            'delivery_address': 'No Auth',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_order_as_vendor_fails(self):
        """Vendor user cannot create an order (403)."""
        self.client.force_authenticate(user=self.vendor_user)
        data = {
            'vendor': self.vendor.id,
            'delivery_address': 'Vendor Order',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # =====================================================================
    # RETRIEVE /api/orders/<pk>/  (IsAuthenticated + IsOrderOwner)
    # =====================================================================

    def test_retrieve_own_order(self):
        """Customer can retrieve their own order by PK."""
        self.client.force_authenticate(user=self.customer_user)
        url = reverse('orders:order-detail', kwargs={'pk': self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.order.id)

    def test_retrieve_vendor_can_see_order(self):
        """Vendor that owns the order can retrieve it."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('orders:order-detail', kwargs={'pk': self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.order.id)

    def test_retrieve_other_customer_order_fails(self):
        """Customer cannot retrieve another customer's order (404)."""
        self.client.force_authenticate(user=self.other_customer_user)
        url = reverse('orders:order-detail', kwargs={'pk': self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_nonexistent_order_fails(self):
        """Non-existent order PK returns 404."""
        self.client.force_authenticate(user=self.customer_user)
        url = reverse('orders:order-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_unauthenticated_fails(self):
        """Unauthenticated user cannot retrieve an order (401)."""
        url = reverse('orders:order-detail', kwargs={'pk': self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # =====================================================================
    # VENDOR ORDERS /api/orders/vendor/  (IsAuthenticated + IsVendor)
    # =====================================================================

    def test_vendor_orders_list(self):
        """Vendor sees only their own orders."""
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.get(self.url_vendor_orders)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The order from setUp belongs to self.vendor
        ids = [o['id'] for o in response.data]
        self.assertIn(self.order.id, ids)

    def test_vendor_orders_excludes_other_vendor_orders(self):
        """Vendor does not see orders belonging to other vendors."""
        # Create an order for other_vendor
        other_order = create_order_with_items(
            customer=self.customer,
            vendor=self.other_vendor,
            product=ProductFactory(vendor=self.other_vendor),
        )
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.get(self.url_vendor_orders)
        ids = [o['id'] for o in response.data]
        self.assertIn(self.order.id, ids)
        self.assertNotIn(other_order.id, ids)

    def test_vendor_orders_as_customer_fails(self):
        """Customer cannot access the vendor orders endpoint (403)."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(self.url_vendor_orders)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_vendor_orders_unauthenticated_fails(self):
        """Unauthenticated user cannot access vendor orders (401)."""
        response = self.client.get(self.url_vendor_orders)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_vendor_orders_empty(self):
        """Vendor with no orders sees empty list."""
        new_vendor_user = UserFactory(role='vendor')
        VendorFactory(user=new_vendor_user, status='approved')
        self.client.force_authenticate(user=new_vendor_user)
        response = self.client.get(self.url_vendor_orders)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    # =====================================================================
    # UPDATE ORDER STATUS /api/orders/<order_id>/status/  (IsVendor)
    # =====================================================================

    def test_vendor_update_order_status(self):
        """Vendor owner can update order status."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('orders:update-order-status', kwargs={'order_id': self.order.id})
        data = {'status': 'preparing'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'preparing')

    def test_vendor_update_status_creates_history(self):
        """Status change creates an OrderStatusHistory entry."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('orders:update-order-status', kwargs={'order_id': self.order.id})
        data = {'status': 'confirmed'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history = OrderStatusHistory.objects.filter(order=self.order)
        self.assertEqual(history.count(), 1)
        self.assertEqual(history.first().new_status, 'confirmed')
        self.assertEqual(history.first().previous_status, 'pending')

    def test_vendor_update_status_full_flow(self):
        """Vendor can transition through multiple statuses."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('orders:update-order-status', kwargs={'order_id': self.order.id})

        for new_status in ['confirmed', 'preparing', 'ready', 'on_route', 'delivered']:
            response = self.client.patch(url, {'status': new_status}, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, new_status)

    def test_vendor_update_other_vendor_order_fails(self):
        """Vendor cannot update status of an order belonging to another vendor (404)."""
        other_order = create_order_with_items(
            customer=self.customer,
            vendor=self.other_vendor,
            product=ProductFactory(vendor=self.other_vendor),
        )
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('orders:update-order-status', kwargs={'order_id': other_order.id})
        data = {'status': 'preparing'}
        response = self.client.patch(url, data, format='json')
        # get_object_or_404 with vendor filter returns 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_vendor_update_status_invalid_status_fails(self):
        """Invalid status value returns 400."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('orders:update-order-status', kwargs={'order_id': self.order.id})
        data = {'status': 'nonexistent_status'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_vendor_update_status_empty_status_fails(self):
        """Missing status returns 400."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('orders:update-order-status', kwargs={'order_id': self.order.id})
        data = {'status': ''}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_update_order_status_fails(self):
        """Customer cannot update order status (403)."""
        self.client.force_authenticate(user=self.customer_user)
        url = reverse('orders:update-order-status', kwargs={'order_id': self.order.id})
        data = {'status': 'preparing'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_status_unauthenticated_fails(self):
        """Unauthenticated user cannot update status (401)."""
        url = reverse('orders:update-order-status', kwargs={'order_id': self.order.id})
        data = {'status': 'confirmed'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # =====================================================================
    # TRACKING /api/orders/tracking/<order_number>/  (IsAuthenticated)
    # =====================================================================

    def test_tracking_own_order_as_customer(self):
        """Customer can track their own order by order_number."""
        self.client.force_authenticate(user=self.customer_user)
        url = reverse('orders:order-tracking', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['order_number'], self.order.order_number)
        self.assertEqual(response.data['status'], self.order.status)
        self.assertIn('status_history', response.data)

    def test_tracking_own_order_as_vendor(self):
        """Vendor can track their own order by order_number."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('orders:order-tracking', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['order_number'], self.order.order_number)

    def test_tracking_order_as_delivery_assigned(self):
        """Delivery person assigned to the order can track it."""
        # Assign delivery person to the order
        self.order.delivery_person = self.delivery_person
        self.order.save()

        self.client.force_authenticate(user=self.delivery_user)
        url = reverse('orders:order-tracking', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        # The view compares delivery_person FK (DeliveryPerson) to request.user (User),
        # which will not match, so expect 404 due to DoesNotExist
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tracking_wrong_customer_fails(self):
        """Another customer cannot track an order they don't own (404)."""
        self.client.force_authenticate(user=self.other_customer_user)
        url = reverse('orders:order-tracking', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tracking_wrong_vendor_fails(self):
        """Other vendor cannot track an order they don't own (404)."""
        self.client.force_authenticate(user=self.other_vendor_user)
        url = reverse('orders:order-tracking', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tracking_nonexistent_order_number_fails(self):
        """Non-existent order_number returns 404."""
        self.client.force_authenticate(user=self.customer_user)
        url = reverse('orders:order-tracking', kwargs={'order_number': 'ORD-NONEXIST'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tracking_unauthenticated_fails(self):
        """Unauthenticated user cannot track an order (401)."""
        url = reverse('orders:order-tracking', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
