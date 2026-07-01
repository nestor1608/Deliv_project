"""
Comprehensive API tests for the AUTH app (users).
Covers registration, login, token management, profile, password change, and password reset.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from tests.factories import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import UserFactory

User = get_user_model()


class AuthRegisterTests(APITestCase):
    """Tests for POST /api/auth/register/"""

    def setUp(self):
        self.url = '/api/auth/register/'
        self.valid_payload = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'StrongPass1!',
            'password_confirm': 'StrongPass1!',
            'first_name': 'New',
            'last_name': 'User',
            'phone_number': '+5493644123999',
            'role': 'customer',
        }

    def test_register_user_success(self):
        """Register a new customer user successfully — returns 201 with tokens."""
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['username'], 'newuser')
        self.assertEqual(response.data['user']['role'], 'customer')
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_register_user_vendor_role_success(self):
        """Register a vendor user successfully."""
        payload = {**self.valid_payload, 'username': 'newvendor', 'role': 'vendor'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['role'], 'vendor')

    def test_register_user_delivery_role_success(self):
        """Register a delivery user successfully."""
        payload = {**self.valid_payload, 'username': 'newdelivery', 'role': 'delivery'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['role'], 'delivery')

    def test_register_duplicate_username(self):
        """Register with an existing username returns 400."""
        UserFactory(username='existing_user')
        payload = {**self.valid_payload, 'username': 'existing_user'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    def test_register_duplicate_email(self):
        """Register with an existing email returns 400."""
        UserFactory(email='taken@example.com')
        payload = {**self.valid_payload, 'email': 'taken@example.com'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_register_password_mismatch(self):
        """Register with mismatched passwords returns 400."""
        payload = {**self.valid_payload, 'password_confirm': 'DifferentPass1!'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data) or self.assertTrue(
            any('contraseñas no coinciden' in str(v).lower()
                for v in response.data.values())
        )

    def test_register_missing_required_fields(self):
        """Register with missing required fields returns 400."""
        payload = {'username': 'incomplete'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_short_password(self):
        """Register with a password shorter than 8 characters returns 400."""
        payload = {**self.valid_payload, 'password': 'Ab1!', 'password_confirm': 'Ab1!'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AuthLoginTests(APITestCase):
    """Tests for POST /api/auth/token/"""

    def setUp(self):
        self.url = '/api/auth/token/'
        self.user = UserFactory(
            username='logintest',
            email='login@example.com',
            password='TestPass123!',
            role='customer',
            status='active',
        )

    def test_login_with_username(self):
        """Login with username returns 200 and JWT tokens."""
        response = self.client.post(self.url, {
            'username_or_email': 'logintest',
            'password': 'TestPass123!',
            'user_type': 'customer',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)

    def test_login_with_email(self):
        """Login with email returns 200 and JWT tokens."""
        response = self.client.post(self.url, {
            'username_or_email': 'login@example.com',
            'password': 'TestPass123!',
            'user_type': 'customer',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_login_wrong_password(self):
        """Login with wrong password returns 400."""
        response = self.client.post(self.url, {
            'username_or_email': 'logintest',
            'password': 'WrongPass123!',
            'user_type': 'customer',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_login_inactive_user(self):
        """Login with an inactive user returns 400."""
        self.user.status = 'inactive'
        self.user.save()
        response = self.client.post(self.url, {
            'username_or_email': 'logintest',
            'password': 'TestPass123!',
            'user_type': 'customer',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_wrong_role(self):
        """Login with mismatched role returns 400."""
        response = self.client.post(self.url, {
            'username_or_email': 'logintest',
            'password': 'TestPass123!',
            'user_type': 'vendor',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_nonexistent_user(self):
        """Login with a non-existent username returns 400."""
        response = self.client.post(self.url, {
            'username_or_email': 'nobody',
            'password': 'TestPass123!',
            'user_type': 'customer',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_missing_username_or_email(self):
        """Login without username_or_email returns 400."""
        response = self.client.post(self.url, {
            'password': 'TestPass123!',
            'user_type': 'customer',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AuthTokenRefreshTests(APITestCase):
    """Tests for POST /api/auth/token/refresh/"""

    def setUp(self):
        self.url = '/api/auth/token/refresh/'
        self.user = UserFactory()

    def test_refresh_valid_token(self):
        """Refresh with a valid refresh token returns 200 with a new access token."""
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(self.url, {
            'refresh': str(refresh),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_refresh_invalid_token(self):
        """Refresh with an invalid refresh token returns 401 or 400."""
        response = self.client.post(self.url, {
            'refresh': 'totally-invalid-token',
        }, format='json')
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_400_BAD_REQUEST,
        ])


class AuthTokenVerifyTests(APITestCase):
    """Tests for POST /api/auth/token/verify/"""

    def setUp(self):
        self.url = '/api/auth/token/verify/'
        self.user = UserFactory()

    def test_verify_valid_token(self):
        """Verify a valid access token returns 200."""
        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)
        response = self.client.post(self.url, {
            'token': access,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_verify_invalid_token(self):
        """Verify an invalid (expired or bogus) token returns 401 (SimpleJWT default)."""
        response = self.client.post(self.url, {
            'token': 'bogus-access-token',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthLogoutTests(APITestCase):
    """Tests for POST /api/auth/logout/"""

    def setUp(self):
        self.url = '/api/auth/logout/'
        self.user = UserFactory()

    def test_logout_with_valid_refresh_token(self):
        """Logout with a valid refresh token returns 200."""
        self.client.force_authenticate(user=self.user)
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(self.url, {
            'refresh_token': str(refresh),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)

    def test_logout_without_token(self):
        """Logout without providing a refresh token still succeeds — returns 200."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_unauthenticated(self):
        """Logout without authentication returns 401."""
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthProfileGetTests(APITestCase):
    """Tests for GET /api/auth/profile/"""

    def setUp(self):
        self.url = '/api/auth/profile/'
        self.user = UserFactory(
            first_name='Profile',
            last_name='Test',
            email='profile@example.com',
        )

    def test_get_profile_authenticated(self):
        """Authenticated user can retrieve their own profile — returns 200."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], self.user.username)
        self.assertEqual(response.data['email'], self.user.email)

    def test_get_profile_unauthenticated(self):
        """Unauthenticated request returns 401."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthProfileUpdateTests(APITestCase):
    """Tests for PATCH /api/auth/profile/"""

    def setUp(self):
        self.url = '/api/auth/profile/'
        self.user = UserFactory(
            first_name='Original',
            last_name='User',
            email='original@example.com',
        )
        self.client.force_authenticate(user=self.user)

    def test_update_allowed_fields_success(self):
        """Update first_name, last_name, and email — returns 200."""
        response = self.client.patch(self.url, {
            'first_name': 'Updated',
            'last_name': 'Name',
            'email': 'updated@example.com',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')
        self.assertEqual(self.user.email, 'updated@example.com')

    def test_update_restricted_field_username(self):
        """Attempting to update username returns 400."""
        response = self.client.patch(self.url, {
            'username': 'newusername',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_restricted_field_role(self):
        """Attempting to update role returns 400."""
        response = self.client.patch(self.url, {
            'role': 'vendor',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_restricted_field_status(self):
        """Attempting to update status returns 400."""
        response = self.client.patch(self.url, {
            'status': 'inactive',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AuthChangePasswordTests(APITestCase):
    """Tests for PATCH /api/auth/change-password/"""

    def setUp(self):
        self.url = '/api/auth/change-password/'
        self.user = UserFactory(password='OldPass123!')
        self.client.force_authenticate(user=self.user)

    def test_change_password_success(self):
        """Change password with correct old password — returns 200."""
        response = self.client.patch(self.url, {
            'old_password': 'OldPass123!',
            'new_password': 'NewStr0ng!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStr0ng!'))

    def test_change_password_wrong_old_password(self):
        """Change password with incorrect old password returns 400."""
        response = self.client.patch(self.url, {
            'old_password': 'WrongOldPass!',
            'new_password': 'NewStr0ng!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_same_as_old(self):
        """Change password to the same password returns 400."""
        response = self.client.patch(self.url, {
            'old_password': 'OldPass123!',
            'new_password': 'OldPass123!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_too_short(self):
        """Change password to a password shorter than 8 chars returns 400."""
        response = self.client.patch(self.url, {
            'old_password': 'OldPass123!',
            'new_password': 'Sh0rt!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_unauthenticated(self):
        """Unauthenticated password change returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.patch(self.url, {
            'old_password': 'OldPass123!',
            'new_password': 'NewStr0ng!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthPasswordResetRequestTests(APITestCase):
    """Tests for POST /api/auth/password-reset/"""

    def setUp(self):
        self.url = '/api/auth/password-reset/'
        self.user = UserFactory(
            email='resetuser@example.com',
            status='active',
        )

    def test_password_reset_request_existing_user(self):
        """Request password reset for an existing user — returns 200 (generic message)."""
        response = self.client.post(self.url, {
            'email': 'resetuser@example.com',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)

    def test_password_reset_request_nonexistent_user(self):
        """Request password reset for a non-existing email — returns 200 (same generic message)."""
        response = self.client.post(self.url, {
            'email': 'noone@example.com',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)

    def test_password_reset_request_invalid_email_format(self):
        """Request password reset with invalid email format returns 400."""
        response = self.client.post(self.url, {
            'email': 'not-an-email',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AuthPasswordResetConfirmTests(APITestCase):
    """Tests for POST /api/auth/password-reset-confirm/<uidb64>/<token>/"""

    def setUp(self):
        self.user = UserFactory(
            username='resetconfirm',
            email='resetconfirm@example.com',
            password='OldPass123!',
            status='active',
        )
        self.valid_uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.valid_token = default_token_generator.make_token(self.user)
        self.payload = {
            'new_password': 'NewStr0ngPass!',
            'new_password_confirm': 'NewStr0ngPass!',
        }

    def _url(self, uidb64, token):
        return f'/api/auth/password-reset-confirm/{uidb64}/{token}/'

    def test_password_reset_confirm_success(self):
        """Confirm password reset with valid uidb64 and token — returns 200."""
        response = self.client.post(
            self._url(self.valid_uidb64, self.valid_token),
            self.payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStr0ngPass!'))

    def test_password_reset_confirm_invalid_token(self):
        """Confirm password reset with an invalid token returns 400."""
        response = self.client.post(
            self._url(self.valid_uidb64, 'bogus-token'),
            self.payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_invalid_uid(self):
        """Confirm password reset with an invalid uidb64 returns 400."""
        response = self.client.post(
            self._url('invalid-uid', self.valid_token),
            self.payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_password_mismatch(self):
        """Confirm password reset with mismatched new passwords returns 400."""
        payload = {
            'new_password': 'NewStr0ngPass!',
            'new_password_confirm': 'DifferentPass1!',
        }
        response = self.client.post(
            self._url(self.valid_uidb64, self.valid_token),
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_short_password(self):
        """Confirm password reset with a password shorter than 8 chars returns 400."""
        payload = {
            'new_password': 'Sh0rt!',
            'new_password_confirm': 'Sh0rt!',
        }
        response = self.client.post(
            self._url(self.valid_uidb64, self.valid_token),
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
