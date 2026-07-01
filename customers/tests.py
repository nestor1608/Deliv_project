"""
Comprehensive API tests for the CUSTOMERS app.
Covers customer profile and address management.
"""
from tests.factories import APITestCase
from rest_framework import status

from tests.factories import UserFactory, CustomerFactory, CustomerAddressFactory

# ---------------------------------------------------------------------------
# Customer Profile
# ---------------------------------------------------------------------------

class CustomerProfileRetrieveTests(APITestCase):
    """Tests for GET /api/customers/profile/"""

    def setUp(self):
        self.url = '/api/customers/profile/'

    def test_get_profile_when_exists(self):
        """Authenticated customer retrieves their existing profile — returns 200."""
        user = UserFactory(role='customer')
        CustomerFactory(user=user, date_of_birth='1990-01-15', is_premium=True)
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user_info', response.data)
        self.assertEqual(response.data['user_info']['username'], user.username)
        self.assertTrue(response.data['is_premium'])

    def test_get_profile_when_not_exists_auto_creates(self):
        """Customer without a profile auto-creates one on GET — returns 200."""
        user = UserFactory(role='customer')
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user_info', response.data)
        self.assertEqual(response.data['loyalty_points'], 0)

    def test_get_profile_unauthenticated(self):
        """Unauthenticated request returns 401."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_profile_as_vendor_user(self):
        """A vendor user can also access the customer profile endpoint (auto-create)."""
        user = UserFactory(role='vendor')
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user_info', response.data)


class CustomerProfileUpdateTests(APITestCase):
    """Tests for PATCH /api/customers/profile/"""

    def setUp(self):
        self.user = UserFactory(role='customer')
        self.customer = CustomerFactory(user=self.user)
        self.url = '/api/customers/profile/'
        self.client.force_authenticate(user=self.user)

    def test_update_date_of_birth(self):
        """Update date_of_birth — returns 200 and reflects the change."""
        response = self.client.patch(self.url, {
            'date_of_birth': '1995-06-20',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertEqual(str(self.customer.date_of_birth), '1995-06-20')

    def test_update_preferred_payment_method(self):
        """Update preferred_payment_method to 'card' — returns 200."""
        response = self.client.patch(self.url, {
            'preferred_payment_method': 'card',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.preferred_payment_method, 'card')

    def test_update_is_premium(self):
        """Update is_premium to True — returns 200."""
        response = self.client.patch(self.url, {
            'is_premium': True,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_premium)

    def test_update_cannot_change_loyalty_points(self):
        """Attempting to update read-only loyalty_points is ignored or returns 200 (field is read-only)."""
        response = self.client.patch(self.url, {
            'loyalty_points': 9999,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.loyalty_points, 0)

    def test_update_unauthenticated(self):
        """Unauthenticated PATCH returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.patch(self.url, {
            'date_of_birth': '1995-06-20',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Customer Addresses – List / Create
# ---------------------------------------------------------------------------

class CustomerAddressListTests(APITestCase):
    """Tests for GET /api/customers/addresses/"""

    def setUp(self):
        self.url = '/api/customers/addresses/'
        self.user = UserFactory(role='customer')
        self.customer = CustomerFactory(user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_list_addresses_empty(self):
        """Customer with no addresses returns an empty list."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])

    def test_list_addresses_with_data(self):
        """Customer with addresses returns all their addresses."""
        CustomerAddressFactory(customer=self.customer, label='Home')
        CustomerAddressFactory(customer=self.customer, label='Work')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_addresses_unauthenticated(self):
        """Unauthenticated request returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_addresses_other_customer_not_visible(self):
        """Addresses belonging to another customer are not visible."""
        other_user = UserFactory(role='customer')
        other_customer = CustomerFactory(user=other_user)
        CustomerAddressFactory(customer=other_customer, label='Secret')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)


class CustomerAddressCreateTests(APITestCase):
    """Tests for POST /api/customers/addresses/"""

    def setUp(self):
        self.url = '/api/customers/addresses/'
        self.user = UserFactory(role='customer')
        self.customer = CustomerFactory(user=self.user)
        self.client.force_authenticate(user=self.user)
        self.valid_payload = {
            'label': 'Home',
            'street_address': 'Av. Siempre Viva 123',
            'city': 'Springfield',
            'state': 'BS',
            'postal_code': '1234',
            'country': 'Argentina',
        }

    def test_create_address_success(self):
        """Create a new address with valid data — returns 201."""
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['label'], 'Home')
        self.assertEqual(response.data['street_address'], 'Av. Siempre Viva 123')
        self.assertFalse(response.data['is_default'])

    def test_create_address_missing_required_fields(self):
        """Create address without required fields returns 400."""
        response = self.client.post(self.url, {'label': 'Incomplete'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_address_set_as_default(self):
        """Create an address marked as default — returns 201, is_default=True."""
        payload = {**self.valid_payload, 'is_default': True}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_default'])

    def test_create_address_default_unsets_previous_default(self):
        """Creating a new default address unsets the previous default."""
        CustomerAddressFactory(customer=self.customer, label='Old Default', is_default=True)
        payload = {**self.valid_payload, 'label': 'New Default', 'is_default': True}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Old default should now be False
        old_default = self.customer.addresses.get(label='Old Default')
        self.assertFalse(old_default.is_default)

    def test_create_address_unauthenticated(self):
        """Unauthenticated POST returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Customer Addresses – Detail (Retrieve / Update / Delete)
# ---------------------------------------------------------------------------

class CustomerAddressDetailRetrieveTests(APITestCase):
    """Tests for GET /api/customers/addresses/<pk>/"""

    def setUp(self):
        self.user = UserFactory(role='customer')
        self.customer = CustomerFactory(user=self.user)
        self.address = CustomerAddressFactory(customer=self.customer, label='Casa')
        self.url = f'/api/customers/addresses/{self.address.pk}/'
        self.client.force_authenticate(user=self.user)

    def test_get_address_success(self):
        """Retrieve an existing address — returns 200."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['label'], 'Casa')

    def test_get_address_non_existent(self):
        """Retrieve a non-existent address returns 404."""
        response = self.client.get('/api/customers/addresses/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_address_other_customer_not_found(self):
        """Retrieve an address belonging to another customer returns 404 (filtered by queryset)."""
        other_user = UserFactory(role='customer')
        other_customer = CustomerFactory(user=other_user)
        other_address = CustomerAddressFactory(customer=other_customer, label='Secret')
        response = self.client.get(f'/api/customers/addresses/{other_address.pk}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_address_unauthenticated(self):
        """Unauthenticated GET returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CustomerAddressUpdateTests(APITestCase):
    """Tests for PUT / PATCH /api/customers/addresses/<pk>/"""

    def setUp(self):
        self.user = UserFactory(role='customer')
        self.customer = CustomerFactory(user=self.user)
        self.address = CustomerAddressFactory(
            customer=self.customer,
            label='Old Label',
            street_address='Old Street 456',
        )
        self.url = f'/api/customers/addresses/{self.address.pk}/'
        self.client.force_authenticate(user=self.user)

    def test_put_address_full_update(self):
        """Fully replace an address via PUT — returns 200."""
        response = self.client.put(self.url, {
            'label': 'New Label',
            'street_address': 'New Street 789',
            'city': 'New City',
            'state': 'NS',
            'postal_code': '5678',
            'country': 'Argentina',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.address.refresh_from_db()
        self.assertEqual(self.address.label, 'New Label')
        self.assertEqual(self.address.street_address, 'New Street 789')

    def test_patch_address_partial_update(self):
        """Partially update an address via PATCH — returns 200."""
        response = self.client.patch(self.url, {
            'label': 'Updated Label',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.address.refresh_from_db()
        self.assertEqual(self.address.label, 'Updated Label')
        # Other fields unchanged
        self.assertEqual(self.address.street_address, 'Old Street 456')

    def test_update_address_set_default(self):
        """Update an address and set it as default — previous default is unset."""
        other_default = CustomerAddressFactory(
            customer=self.customer, label='Other', is_default=True
        )
        response = self.client.patch(self.url, {'is_default': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.address.refresh_from_db()
        self.assertTrue(self.address.is_default)
        other_default.refresh_from_db()
        self.assertFalse(other_default.is_default)

    def test_update_address_unauthenticated(self):
        """Unauthenticated update returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.patch(self.url, {'label': 'Hacked'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_address_other_customer_not_found(self):
        """Update on an address belonging to another customer returns 404."""
        other_user = UserFactory(role='customer')
        other_customer = CustomerFactory(user=other_user)
        other_address = CustomerAddressFactory(customer=other_customer, label='Other')
        response = self.client.patch(
            f'/api/customers/addresses/{other_address.pk}/',
            {'label': 'Stolen'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CustomerAddressDeleteTests(APITestCase):
    """Tests for DELETE /api/customers/addresses/<pk>/"""

    def setUp(self):
        self.user = UserFactory(role='customer')
        self.customer = CustomerFactory(user=self.user)
        self.address = CustomerAddressFactory(customer=self.customer, label='To Delete')
        self.url = f'/api/customers/addresses/{self.address.pk}/'
        self.client.force_authenticate(user=self.user)

    def test_delete_own_address_success(self):
        """Delete an address the customer owns — returns 204."""
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            self.customer.addresses.filter(pk=self.address.pk).exists()
        )

    def test_delete_address_unauthenticated(self):
        """Unauthenticated DELETE returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_other_customer_address_not_found(self):
        """DELETE on an address belonging to another customer returns 404 (not in queryset)."""
        other_user = UserFactory(role='customer')
        other_customer = CustomerFactory(user=other_user)
        other_address = CustomerAddressFactory(customer=other_customer, label='Other')
        response = self.client.delete(
            f'/api/customers/addresses/{other_address.pk}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_non_existent_address(self):
        """DELETE on a non-existent address returns 404."""
        response = self.client.delete('/api/customers/addresses/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
