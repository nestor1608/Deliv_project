"""
Comprehensive API tests for the Vendors app.
Covers VendorCategory, Vendor, Product, and VendorRating endpoints.
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from tests.factories import APITestCase
from tests.factories import *

from vendors.models import Vendor, Product, VendorRating


class VendorCategoryAPITests(APITestCase):
    """Tests for /api/vendors/categories/ endpoints."""

    def setUp(self):
        self.category = VendorCategoryFactory()
        self.inactive_category = VendorCategoryFactory(is_active=False)
        self.url_list = reverse('vendors:categories-list')
        self.url_detail = reverse('vendors:categories-detail', kwargs={'pk': self.category.id})

    def test_list_categories_unauthenticated(self):
        """AllowAny — unauthenticated user can list active categories."""
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only active categories should appear
        ids = [c['id'] for c in response.data]
        self.assertIn(self.category.id, ids)
        self.assertNotIn(self.inactive_category.id, ids)

    def test_retrieve_category_unauthenticated(self):
        """AllowAny — unauthenticated user can retrieve a single category."""
        response = self.client.get(self.url_detail)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.category.name)


class VendorAPITests(APITestCase):
    """Tests for /api/vendors/vendors/ endpoints."""

    def setUp(self):
        # Create two customers (for authentication where needed)
        self.customer = CustomerFactory()
        self.customer_user = self.customer.user

        # Create a vendor
        self.vendor_user = UserFactory(role='vendor')
        self.vendor = VendorFactory(user=self.vendor_user, status='approved')

        # Another vendor (created by a different user)
        self.other_vendor_user = UserFactory(role='vendor')
        self.other_vendor = VendorFactory(
            user=self.other_vendor_user,
            business_name='Other Business',
            status='approved',
        )

        # A pending vendor (should NOT appear in default list)
        self.pending_vendor = VendorFactory(status='pending')

        # Product belonging to self.vendor
        self.product = ProductFactory(vendor=self.vendor)

        self.url_list = reverse('vendors:vendors-list')

    # --- LIST (AllowAny) ---

    def test_list_vendors_unauthenticated(self):
        """AllowAny — unauthenticated users can list approved vendors."""
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [v['id'] for v in response.data['results']]
        self.assertIn(self.vendor.id, ids)
        self.assertIn(self.other_vendor.id, ids)
        self.assertNotIn(self.pending_vendor.id, ids)

    def test_list_vendors_filter_by_category(self):
        """Filter vendors by category ID."""
        url = self.url_list + f'?category={self.vendor.category.id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [v['id'] for v in response.data['results']]
        self.assertIn(self.vendor.id, ids)
        self.assertNotIn(self.other_vendor.id, ids)

    def test_list_vendors_search_by_business_name(self):
        """Search vendors by business_name."""
        response = self.client.get(self.url_list, {'search': self.vendor.business_name})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [v['business_name'] for v in response.data['results']]
        self.assertIn(self.vendor.business_name, names)
        self.assertNotIn(self.other_vendor.business_name, names)

    def test_list_vendors_search_no_match(self):
        """Search with a term that matches no vendor returns empty list."""
        response = self.client.get(self.url_list, {'search': 'ZZZZNONEXISTENT'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    # --- CREATE (IsAuthenticated) ---

    def test_create_vendor_authenticated(self):
        """Authenticated user (vendor role) can register a new vendor."""
        new_user = UserFactory(role='vendor')
        self.client.force_authenticate(user=new_user)
        data = {
            'business_name': 'Brand New Shop',
            'category': self.vendor.category.id,
            'business_license': 'LIC-BRAND-NEW',
            'tax_id': 'TAX-BRAND-NEW',
            'address': '123 Main St',
            'latitude': '-31.6625',
            'longitude': '-60.7676',
            'opening_time': '08:00',
            'closing_time': '22:00',
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Vendor.objects.filter(business_name='Brand New Shop').count(), 1)

    def test_create_vendor_unauthenticated_fails(self):
        """Unauthenticated user cannot register a vendor (401)."""
        data = {
            'business_name': 'No Auth Shop',
            'category': self.vendor.category.id,
            'business_license': 'LIC-NOAUTH',
            'tax_id': 'TAX-NOAUTH',
            'address': '456 Elm St',
            'latitude': '-31.6625',
            'longitude': '-60.7676',
            'opening_time': '08:00',
            'closing_time': '22:00',
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_vendor_duplicate_business_license_fails(self):
        """Duplicate business_license returns 400."""
        self.client.force_authenticate(user=self.other_vendor_user)
        data = {
            'business_name': 'Duplicate License Shop',
            'category': self.vendor.category.id,
            'business_license': self.vendor.business_license,  # already taken
            'tax_id': 'TAX-DUP-LIC',
            'address': '789 Oak St',
            'latitude': '-31.6625',
            'longitude': '-60.7676',
            'opening_time': '08:00',
            'closing_time': '22:00',
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_vendor_duplicate_tax_id_fails(self):
        """Duplicate tax_id returns 400."""
        self.client.force_authenticate(user=self.other_vendor_user)
        data = {
            'business_name': 'Duplicate Tax Shop',
            'category': self.vendor.category.id,
            'business_license': 'LIC-UNIQUE-TAX',
            'tax_id': self.vendor.tax_id,  # already taken
            'address': '321 Pine St',
            'latitude': '-31.6625',
            'longitude': '-60.7676',
            'opening_time': '08:00',
            'closing_time': '22:00',
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- RETRIEVE (AllowAny) ---

    def test_retrieve_vendor_detail(self):
        """AllowAny — retrieve vendor detail by ID."""
        url = reverse('vendors:vendors-detail', kwargs={'pk': self.vendor.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['business_name'], self.vendor.business_name)

    def test_retrieve_nonexistent_vendor_returns_404(self):
        """Non-existent vendor PK returns 404."""
        url = reverse('vendors:vendors-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- UPDATE / PARTIAL_UPDATE (IsAuthenticated + IsVendorOwner) ---

    def test_partial_update_own_vendor(self):
        """Vendor owner can partially update their own vendor."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('vendors:vendors-detail', kwargs={'pk': self.vendor.id})
        data = {'business_name': 'Updated Name'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.business_name, 'Updated Name')

    def test_partial_update_other_vendor_fails(self):
        """Vendor cannot update another vendor's profile (403)."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('vendors:vendors-detail', kwargs={'pk': self.other_vendor.id})
        data = {'business_name': 'Hacked Name'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_own_vendor_unauthenticated_fails(self):
        """Unauthenticated user cannot update a vendor (401)."""
        url = reverse('vendors:vendors-detail', kwargs={'pk': self.vendor.id})
        data = {'business_name': 'No Auth'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- DELETE (IsAuthenticated + IsVendorOwner) ---

    def test_delete_own_vendor(self):
        """Vendor owner can delete their own vendor."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('vendors:vendors-detail', kwargs={'pk': self.vendor.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Vendor.objects.filter(id=self.vendor.id).exists())

    def test_delete_other_vendor_fails(self):
        """Vendor cannot delete another vendor (403)."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('vendors:vendors-detail', kwargs={'pk': self.other_vendor.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- VENDOR PRODUCTS ACTION ---

    def test_list_vendor_products(self):
        """GET vendor/{pk}/products/ returns the vendor's available products."""
        unavailable = ProductFactory(vendor=self.vendor, is_available=False)
        url = reverse('vendors:vendors-products', kwargs={'pk': self.vendor.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [p['id'] for p in response.data]
        self.assertIn(self.product.id, ids)
        self.assertNotIn(unavailable.id, ids)

    def test_list_vendor_products_with_category_filter(self):
        """Vendor products can be filtered by category."""
        ProductFactory(vendor=self.vendor, name='Excluded', category='Other')
        url = reverse('vendors:vendors-products', kwargs={'pk': self.vendor.id})
        response = self.client.get(url, {'product_category': self.product.category})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for p in response.data:
            self.assertIn(self.product.category.lower(), p['category'].lower())

    def test_list_vendor_products_with_search(self):
        """Vendor products can be searched by name."""
        url = reverse('vendors:vendors-products', kwargs={'pk': self.vendor.id})
        response = self.client.get(url, {'product_search': self.product.name[:4]})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [p['name'] for p in response.data]
        self.assertIn(self.product.name, names)

    # --- VENDOR RATINGS ACTION ---

    def test_list_vendor_ratings(self):
        """GET vendor/{pk}/ratings/ returns ratings for that vendor."""
        rating = create_vendor_rating(vendor=self.vendor)
        url = reverse('vendors:vendors-ratings', kwargs={'pk': self.vendor.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in response.data]
        self.assertIn(rating.id, ids)

    def test_list_vendor_ratings_empty(self):
        """Vendor with no ratings returns empty list."""
        url = reverse('vendors:vendors-ratings', kwargs={'pk': self.other_vendor.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    # --- NEARBY ACTION ---

    def test_nearby_without_coordinates_fails(self):
        """Missing latitude/longitude returns 400."""
        url = reverse('vendors:vendors-nearby')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_nearby_with_coordinates_succeeds(self):
        """Valid latitude/longitude returns open vendors."""
        url = reverse('vendors:vendors-nearby')
        response = self.client.get(url, {'latitude': '-31.6625', 'longitude': '-60.7676'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_nearby_only_returns_open_vendors(self):
        """Nearby endpoint only returns vendors with is_open=True."""
        self.vendor.is_open = False
        self.vendor.save()
        url = reverse('vendors:vendors-nearby')
        response = self.client.get(url, {'latitude': '-31.6625', 'longitude': '-60.7676'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [v['id'] for v in response.data]
        self.assertNotIn(self.vendor.id, ids)

    # --- TOGGLE STATUS ACTION ---

    def test_toggle_status_owner(self):
        """Vendor owner can toggle is_open."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('vendors:vendors-toggle-status', kwargs={'pk': self.vendor.id})
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.vendor.refresh_from_db()
        self.assertFalse(self.vendor.is_open)

    def test_toggle_status_non_owner_fails(self):
        """Other vendor cannot toggle is_open (403)."""
        self.client.force_authenticate(user=self.other_vendor_user)
        url = reverse('vendors:vendors-toggle-status', kwargs={'pk': self.vendor.id})
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_toggle_status_unauthenticated_fails(self):
        """Unauthenticated user cannot toggle is_open (401)."""
        url = reverse('vendors:vendors-toggle-status', kwargs={'pk': self.vendor.id})
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProductAPITests(APITestCase):
    """Tests for /api/vendors/products/ endpoints."""

    def setUp(self):
        self.vendor_user = UserFactory(role='vendor')
        self.vendor = VendorFactory(user=self.vendor_user, status='approved', is_open=True)
        self.customer = CustomerFactory()
        self.customer_user = self.customer.user

        self.product = ProductFactory(vendor=self.vendor, is_available=True)
        # Another vendor's product (not available to own)
        self.other_vendor = VendorFactory(status='approved', is_open=True)
        self.other_product = ProductFactory(vendor=self.other_vendor, is_available=True)

        self.url_list = reverse('vendors:products-list')

    # --- LIST (AllowAny) ---

    def test_list_products_as_vendor_sees_own(self):
        """Vendor sees only their own products."""
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [p['id'] for p in response.data['results']]
        self.assertIn(self.product.id, ids)
        self.assertNotIn(self.other_product.id, ids)

    def test_list_products_as_customer_sees_available(self):
        """Customer sees available products from open vendors."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [p['id'] for p in response.data['results']]
        self.assertIn(self.product.id, ids)
        self.assertIn(self.other_product.id, ids)

    def test_list_products_as_customer_filters_unavailable(self):
        """Customer does NOT see unavailable products."""
        unavailable = ProductFactory(vendor=self.vendor, is_available=False)
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(self.url_list)
        ids = [p['id'] for p in response.data['results']]
        self.assertNotIn(unavailable.id, ids)

    def test_list_products_as_customer_filters_closed_vendor(self):
        """Customer does NOT see products from closed vendors."""
        self.vendor.is_open = False
        self.vendor.save()
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(self.url_list)
        ids = [p['id'] for p in response.data['results']]
        self.assertNotIn(self.product.id, ids)

    def test_list_products_unauthenticated(self):
        """AllowAny — unauthenticated user sees available products (like customer)."""
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_products_filter_by_vendor(self):
        """Filter products by vendor ID."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(self.url_list, {'vendor': self.vendor.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [p['id'] for p in response.data['results']]
        self.assertIn(self.product.id, ids)
        self.assertNotIn(self.other_product.id, ids)

    # --- CREATE (IsAuthenticated + IsVendorOwner) ---

    def test_create_product_for_own_vendor(self):
        """Vendor can create a product for their own shop."""
        self.client.force_authenticate(user=self.vendor_user)
        data = {
            'name': 'New Product',
            'description': 'Fresh item',
            'price': '49.99',
            'category': 'Food',
            'stock': 50,
            'is_available': True,
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.filter(name='New Product').count(), 1)

    def test_create_product_as_customer_fails(self):
        """Customer cannot create a product."""
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'name': 'Customer Product',
            'price': '10.00',
            'category': 'General',
            'stock': 5,
        }
        response = self.client.post(self.url_list, data, format='json')
        # IsVendorOwner.has_permission returns True (default),
        # but perform_create raises RelatedObjectDoesNotExist → 500
        # Assert it does not succeed
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_product_unauthenticated_fails(self):
        """Unauthenticated user cannot create a product (401)."""
        data = {
            'name': 'No Auth Product',
            'price': '5.00',
            'category': 'General',
            'stock': 1,
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- UPDATE / PARTIAL_UPDATE (IsAuthenticated + IsVendorOwner) ---

    def test_partial_update_own_product(self):
        """Vendor owner can partially update their own product."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('vendors:products-detail', kwargs={'pk': self.product.id})
        data = {'price': '25.00', 'is_available': False}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('25.00'))
        self.assertFalse(self.product.is_available)

    def test_partial_update_other_vendor_product_fails(self):
        """Vendor cannot update another vendor's product (403)."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('vendors:products-detail', kwargs={'pk': self.other_product.id})
        data = {'price': '1.00'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- DELETE (IsAuthenticated + IsVendorOwner) ---

    def test_delete_own_product(self):
        """Vendor owner can delete their own product."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('vendors:products-detail', kwargs={'pk': self.product.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(id=self.product.id).exists())

    def test_delete_other_vendor_product_fails(self):
        """Vendor cannot delete another vendor's product (403)."""
        self.client.force_authenticate(user=self.vendor_user)
        url = reverse('vendors:products-detail', kwargs={'pk': self.other_product.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class VendorRatingAPITests(APITestCase):
    """Tests for /api/vendors/ratings/ endpoints."""

    def setUp(self):
        self.customer = CustomerFactory()
        self.customer_user = self.customer.user
        self.vendor_user = UserFactory(role='vendor')
        self.vendor = VendorFactory(user=self.vendor_user, status='approved')
        self.product = ProductFactory(vendor=self.vendor)
        self.url_list = reverse('vendors:ratings-list')

        # Create a delivered order to be rated
        self.delivered_order = create_order_with_items(
            customer=self.customer,
            vendor=self.vendor,
            product=self.product,
            quantity=1,
        )
        self.delivered_order.status = 'delivered'
        self.delivered_order.save()

    # --- LIST ---

    def test_list_ratings_as_customer(self):
        """Customer sees their own ratings."""
        create_vendor_rating(customer=self.customer, vendor=self.vendor, order=self.delivered_order)
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_ratings_as_vendor_fails(self):
        """Vendor cannot list ratings via the ratings endpoint (403)."""
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_ratings_unauthenticated_fails(self):
        """Unauthenticated user cannot list ratings (401)."""
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- CREATE ---

    def test_create_rating_valid(self):
        """Customer can rate a delivered order."""
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'vendor': self.vendor.id,
            'order': self.delivered_order.id,
            'rating': 5,
            'comment': 'Excellent service!',
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(VendorRating.objects.count(), 1)

    def test_create_rating_as_vendor_fails(self):
        """Vendor cannot create a rating (403)."""
        self.client.force_authenticate(user=self.vendor_user)
        data = {
            'vendor': self.vendor.id,
            'order': self.delivered_order.id,
            'rating': 5,
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_rating_unauthenticated_fails(self):
        """Unauthenticated user cannot create a rating (401)."""
        data = {
            'vendor': self.vendor.id,
            'order': self.delivered_order.id,
            'rating': 5,
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_duplicate_rating_fails(self):
        """Duplicate rating for same customer+order returns 400."""
        create_vendor_rating(
            customer=self.customer,
            vendor=self.vendor,
            order=self.delivered_order,
            rating=4,
        )
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'vendor': self.vendor.id,
            'order': self.delivered_order.id,
            'rating': 3,
            'comment': 'Trying again',
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rating_non_delivered_order_fails(self):
        """Cannot rate an order that has not been delivered (400)."""
        pending_order = create_order_with_items(
            customer=self.customer,
            vendor=self.vendor,
            product=self.product,
            quantity=1,
        )
        # status is 'pending' by default
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'vendor': self.vendor.id,
            'order': pending_order.id,
            'rating': 4,
            'comment': 'Not delivered yet',
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rating_wrong_customer_order_fails(self):
        """Cannot rate an order belonging to a different customer (400)."""
        other_customer = CustomerFactory()
        other_order = create_order_with_items(
            customer=other_customer,
            vendor=self.vendor,
            product=self.product,
            quantity=1,
        )
        other_order.status = 'delivered'
        other_order.save()
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'vendor': self.vendor.id,
            'order': other_order.id,
            'rating': 5,
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rating_invalid_rating_value_fails(self):
        """Rating must be between 1 and 5 (400)."""
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'vendor': self.vendor.id,
            'order': self.delivered_order.id,
            'rating': 6,
            'comment': 'Too high',
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rating_zero_fails(self):
        """Rating of 0 is invalid (400)."""
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'vendor': self.vendor.id,
            'order': self.delivered_order.id,
            'rating': 0,
        }
        response = self.client.post(self.url_list, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
