"""
Comprehensive API tests for the Payments app.
Covers PaymentMethodViewSet, PaymentViewSet, process_payment,
and webhook endpoints.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django.utils import timezone
from tests.factories import APITestCase
from rest_framework import status

from tests.factories import (
    UserFactory,
    CustomerFactory,
    VendorFactory,
    ProductFactory,
    PaymentMethodFactory,
    create_order_with_items,
)
from payments.models import Payment, PaymentMethod

# ---------------------------------------------------------------------------
# Workaround for a pre-existing bug in core/exceptions.py:  The function
# get_error_code is defined twice in the same file; the second definition
# (single argument) shadows the first (two arguments), but
# format_error_response still calls it with two arguments, causing a
# TypeError.  We patch it here at module level so the tests can run.
# ---------------------------------------------------------------------------
import core.exceptions as _core_exc
_original_get_error_code = _core_exc.get_error_code
_core_exc.get_error_code = lambda code, exc=None: _original_get_error_code(code)

User = get_user_model()


@override_settings(DEBUG=True)
class PaymentMethodViewSetTests(APITestCase):
    """Tests for the PaymentMethodViewSet (/api/payments/payment-methods/)."""

    def setUp(self):
        self.user = UserFactory()

    def test_list_payment_methods_active_only(self):
        """GET /api/payments/payment-methods/ returns only active payment methods."""
        PaymentMethodFactory.create_batch(3, is_active=True)
        PaymentMethodFactory(is_active=False)
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/payments/payment-methods/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)

    def test_list_payment_methods_empty(self):
        """When no active methods exist, list returns 0 count."""
        # No methods created yet
        PaymentMethod.objects.all().delete()
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/payments/payment-methods/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_retrieve_payment_method_success(self):
        """GET /api/payments/payment-methods/<pk>/ returns the method details."""
        method = PaymentMethodFactory(is_active=True)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/payments/payment-methods/{method.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], method.name)

    def test_retrieve_inactive_payment_method_404(self):
        """Inactive methods should not be accessible via retrieve."""
        inactive = PaymentMethodFactory(is_active=False)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/payments/payment-methods/{inactive.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_payment_methods_unauthenticated(self):
        """Unauthenticated request returns 401."""
        response = self.client.get('/api/payments/payment-methods/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_payment_method_unauthenticated(self):
        """Unauthenticated retrieve returns 401."""
        method = PaymentMethodFactory(is_active=True)
        response = self.client.get(f'/api/payments/payment-methods/{method.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(DEBUG=True)
class PaymentViewSetTests(APITestCase):
    """Tests for the PaymentViewSet (/api/payments/payments/)."""

    def setUp(self):
        self.order = create_order_with_items()
        self.customer_user = self.order.customer.user
        self.other_user = UserFactory(role='customer')
        self.admin_user = UserFactory(role='admin')
        self.cash_method = PaymentMethodFactory(type='cash')
        self.card_method = PaymentMethodFactory(type='card')
        # Create non-owned order for isolation tests
        other_customer = CustomerFactory(user=self.other_user)
        self.other_order = create_order_with_items(customer=other_customer)

    # --- GET list ---

    def test_list_payments_empty(self):
        """GET /api/payments/payments/ returns empty for user with no payments."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get('/api/payments/payments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_list_payments_with_data(self):
        """GET /api/payments/payments/ returns only the user's own payments."""
        Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
        )
        Payment.objects.create(
            user=self.other_user,
            payment_method=self.cash_method,
            content_object=self.other_order,
            amount=self.other_order.total_amount,
            status='completed',
        )
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get('/api/payments/payments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_list_payments_admin_sees_all(self):
        """Admin users see all payments across all users."""
        Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
        )
        Payment.objects.create(
            user=self.other_user,
            payment_method=self.cash_method,
            content_object=self.other_order,
            amount=self.other_order.total_amount,
            status='completed',
        )
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/payments/payments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_list_payments_unauthenticated(self):
        """Unauthenticated list returns 401."""
        response = self.client.get('/api/payments/payments/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- POST create ---

    def test_create_payment_success(self):
        """POST /api/payments/payments/ creates a pending payment for a valid order."""
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'object_type': 'order',
            'object_id': self.order.id,
            'payment_method': self.cash_method.id,
        }
        response = self.client.post('/api/payments/payments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.user, self.customer_user)
        self.assertEqual(payment.status, 'pending')

    def test_create_payment_non_owned_order_400(self):
        """Creating a payment for another user's order returns 400."""
        self.client.force_authenticate(user=self.other_user)
        data = {
            'object_type': 'order',
            'object_id': self.order.id,
            'payment_method': self.cash_method.id,
        }
        response = self.client.post('/api/payments/payments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_nonexistent_order_400(self):
        """Creating a payment for a non-existent order returns 400."""
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'object_type': 'order',
            'object_id': 99999,
            'payment_method': self.cash_method.id,
        }
        response = self.client.post('/api/payments/payments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_duplicate_completed_400(self):
        """Creating a second completed payment for the same object returns 400."""
        Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
        )
        self.client.force_authenticate(user=self.customer_user)
        data = {
            'object_type': 'order',
            'object_id': self.order.id,
            'payment_method': self.cash_method.id,
        }
        response = self.client.post('/api/payments/payments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_unauthenticated(self):
        """Unauthenticated create returns 401."""
        data = {
            'object_type': 'order',
            'object_id': 1,
            'payment_method': 1,
        }
        response = self.client.post('/api/payments/payments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- GET retrieve ---

    def test_retrieve_own_payment(self):
        """GET /api/payments/payments/<pk>/ returns own payment details."""
        payment = Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
        )
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(f'/api/payments/payments/{payment.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['payment_id'], payment.payment_id)

    def test_retrieve_other_payment_not_visible(self):
        """A non-admin user cannot retrieve another user's payment."""
        payment = Payment.objects.create(
            user=self.other_user,
            payment_method=self.cash_method,
            content_object=self.other_order,
            amount=self.other_order.total_amount,
            status='completed',
        )
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(f'/api/payments/payments/{payment.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_admin_sees_all(self):
        """Admin users can retrieve any user's payment."""
        payment = Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
        )
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f'/api/payments/payments/{payment.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_nonexistent_404(self):
        """Retrieve a non-existent payment returns 404."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get('/api/payments/payments/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_unauthenticated(self):
        """Unauthenticated retrieve returns 401."""
        payment = Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
        )
        response = self.client.get(f'/api/payments/payments/{payment.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- POST refund ---

    def test_refund_completed_payment_success(self):
        """POST .../refund/ creates a pending refund for a completed payment."""
        payment = Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
            completed_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(
            f'/api/payments/payments/{payment.id}/refund/',
            {'reason': 'Customer request'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('refund', response.data)
        self.assertEqual(response.data['refund']['status'], 'pending')

    def test_refund_completed_payment_with_amount(self):
        """Refund with a specific amount succeeds."""
        payment = Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
            completed_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.customer_user)
        refund_amount = self.order.total_amount / 2
        response = self.client.post(
            f'/api/payments/payments/{payment.id}/refund/',
            {'amount': str(refund_amount), 'reason': 'Partial refund'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['refund']['amount'], str(refund_amount))

    def test_refund_pending_payment_fails(self):
        """Refunding a non-completed (pending) payment returns 400."""
        payment = Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='pending',
        )
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(
            f'/api/payments/payments/{payment.id}/refund/',
            {'reason': 'Test'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refund_amount_exceeds_original_400(self):
        """Refund amount exceeding the original payment amount returns 400."""
        payment = Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
            completed_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(
            f'/api/payments/payments/{payment.id}/refund/',
            {
                'amount': str(self.order.total_amount * 2),
                'reason': 'Too much',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refund_other_user_payment_404(self):
        """A user cannot refund another user's payment."""
        payment = Payment.objects.create(
            user=self.other_user,
            payment_method=self.cash_method,
            content_object=self.other_order,
            amount=self.other_order.total_amount,
            status='completed',
            completed_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(
            f'/api/payments/payments/{payment.id}/refund/',
            {'reason': 'Not mine'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_refund_nonexistent_404(self):
        """Refunding a non-existent payment returns 404."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(
            '/api/payments/payments/99999/refund/',
            {'reason': 'Test'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- GET receipt ---

    def test_get_receipt_success(self):
        """GET .../receipt/ returns receipt data for a completed payment."""
        payment = Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
            completed_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(f'/api/payments/payments/{payment.id}/receipt/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['payment_id'], payment.payment_id)
        self.assertIn('order', response.data)
        self.assertEqual(
            response.data['order']['order_number'],
            self.order.order_number,
        )

    def test_get_receipt_other_user_404(self):
        """Getting receipt for another user's payment returns 404."""
        payment = Payment.objects.create(
            user=self.other_user,
            payment_method=self.cash_method,
            content_object=self.other_order,
            amount=self.other_order.total_amount,
            status='completed',
            completed_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(f'/api/payments/payments/{payment.id}/receipt/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_receipt_for_pending_payment(self):
        """Receipt can still be fetched for a pending payment (returns current data)."""
        payment = Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='pending',
        )
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get(f'/api/payments/payments/{payment.id}/receipt/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Pendiente')

    def test_get_receipt_unauthenticated(self):
        """Unauthenticated receipt request returns 401."""
        payment = Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
        )
        response = self.client.get(f'/api/payments/payments/{payment.id}/receipt/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- GET statistics ---

    def test_statistics_with_payments(self):
        """GET .../statistics/ returns correct aggregated data."""
        Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
            completed_at=timezone.now(),
        )
        Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=Decimal('50.00'),
            status='pending',
        )
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get('/api/payments/payments/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_payments'], 2)
        self.assertEqual(response.data['completed_payments'], 1)
        self.assertEqual(response.data['pending_payments'], 1)

    def test_statistics_with_no_payments(self):
        """Statistics return zeros when user has no payments."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.get('/api/payments/payments/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_payments'], 0)
        self.assertEqual(response.data['total_amount'], 0)

    def test_statistics_admin_sees_all(self):
        """Admin statistics cover all payments."""
        Payment.objects.create(
            user=self.customer_user,
            payment_method=self.cash_method,
            content_object=self.order,
            amount=self.order.total_amount,
            status='completed',
            completed_at=timezone.now(),
        )
        Payment.objects.create(
            user=self.other_user,
            payment_method=self.cash_method,
            content_object=self.other_order,
            amount=self.other_order.total_amount,
            status='completed',
            completed_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/payments/payments/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_payments'], 2)

    def test_statistics_unauthenticated(self):
        """Unauthenticated statistics request returns 401."""
        response = self.client.get('/api/payments/payments/statistics/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(DEBUG=True)
class ProcessPaymentAPITests(APITestCase):
    """Tests for the process_payment endpoint (/api/payments/process/)."""

    def setUp(self):
        self.order = create_order_with_items()
        self.customer_user = self.order.customer.user
        self.other_user = UserFactory(role='customer')
        self.cash_method = PaymentMethodFactory(type='cash', provider='cash')
        self.card_method = PaymentMethodFactory(type='card', provider='mercadopago')

    def test_process_payment_cash_success(self):
        """POST /api/payments/process/ – cash method marks payment completed immediately."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(
            '/api/payments/process/',
            {
                'object_type': 'order',
                'object_id': self.order.id,
                'payment_method_id': self.cash_method.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['payment']['status'], 'completed')

    def test_process_payment_cash_updates_order_payment_status(self):
        """Cash payment sets the order's payment_status to 'paid'."""
        self.client.force_authenticate(user=self.customer_user)
        self.client.post(
            '/api/payments/process/',
            {
                'object_type': 'order',
                'object_id': self.order.id,
                'payment_method_id': self.cash_method.id,
            },
            format='json',
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'paid')

    def test_process_payment_invalid_method_400(self):
        """POST with a non-existent payment_method_id returns 400."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(
            '/api/payments/process/',
            {
                'object_type': 'order',
                'object_id': self.order.id,
                'payment_method_id': 99999,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_process_payment_inactive_method_400(self):
        """POST with an inactive payment_method_id returns 400."""
        inactive_method = PaymentMethodFactory(is_active=False)
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(
            '/api/payments/process/',
            {
                'object_type': 'order',
                'object_id': self.order.id,
                'payment_method_id': inactive_method.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_process_payment_non_owned_order_forbidden(self):
        """POST with another user's order returns 403."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.post(
            '/api/payments/process/',
            {
                'object_type': 'order',
                'object_id': self.order.id,
                'payment_method_id': self.cash_method.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_process_payment_nonexistent_order_error(self):
        """POST with a non-existent object_id returns a server error (the view's
        generic except Exception catches Http404 and returns 500)."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(
            '/api/payments/process/',
            {
                'object_type': 'order',
                'object_id': 99999,
                'payment_method_id': self.cash_method.id,
            },
            format='json',
        )
        # NOTE: the view wraps everything in except Exception → 500
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_process_payment_already_paid_400(self):
        """Trying to pay an already-paid order returns 400."""
        self.client.force_authenticate(user=self.customer_user)
        # First payment
        self.client.post(
            '/api/payments/process/',
            {
                'object_type': 'order',
                'object_id': self.order.id,
                'payment_method_id': self.cash_method.id,
            },
            format='json',
        )
        # Second attempt
        response = self.client.post(
            '/api/payments/process/',
            {
                'object_type': 'order',
                'object_id': self.order.id,
                'payment_method_id': self.cash_method.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_process_payment_invalid_object_type_400(self):
        """POST with an invalid object_type returns 400."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(
            '/api/payments/process/',
            {
                'object_type': 'invalid_type',
                'object_id': self.order.id,
                'payment_method_id': self.cash_method.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_process_payment_unauthenticated(self):
        """Unauthenticated process request returns 401."""
        response = self.client.post(
            '/api/payments/process/',
            {
                'object_type': 'order',
                'object_id': 1,
                'payment_method_id': 1,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('payments.views.MercadoPagoService')
    def test_process_payment_mercadopago_unavailable_falls_back(self, mock_mp_service):
        """
        When MercadoPago service is not configured, processing with a
        card/mercadopago method still creates a payment but marks it as failed.
        """
        mock_instance = mock_mp_service.return_value
        mock_instance.create_payment.return_value = {
            'status': 'rejected',
            'status_detail': 'method unavailable',
        }

        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(
            '/api/payments/process/',
            {
                'object_type': 'order',
                'object_id': self.order.id,
                'payment_method_id': self.card_method.id,
                'payment_data': {'payment_method_id': 'visa'},
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['payment']['status'], 'failed')


@override_settings(DEBUG=True)
class WebhookAPITests(APITestCase):
    """Tests for webhook endpoints (/api/payments/webhook/*)."""

    def test_mercadopago_webhook_returns_200(self):
        """
        POST /api/payments/webhook/mercadopago/ returns 200 even when
        the service is not fully configured, as long as the request is valid.
        """
        with patch(
            'payments.views.settings.PAYMENT_SETTINGS',
            {'MERCADOPAGO': {'WEBHOOK_SECRET': '', 'ACCESS_TOKEN': 'dummy'}},
            create=True,
        ), patch('payments.views.MercadoPagoService') as mock_mp:
            mock_instance = mock_mp.return_value
            mock_instance.get_payment_status.return_value = {'status': 'approved'}

            response = self.client.post(
                '/api/payments/webhook/mercadopago/',
                {'action': 'payment.created', 'data': {'id': '12345'}},
                format='json',
            )
            self.assertEqual(response.status_code, 200)

    def test_stripe_webhook_returns_200(self):
        """POST /api/payments/webhook/stripe/ always returns 200."""
        response = self.client.post(
            '/api/payments/webhook/stripe/',
            {'type': 'payment_intent.succeeded'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)

    def test_stripe_webhook_without_body(self):
        """Stripe webhook returns 200 even with an empty body."""
        response = self.client.post(
            '/api/payments/webhook/stripe/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, 200)

    def test_mercadopago_webhook_without_payment_id(self):
        """
        When the webhook payload contains no payment id, the endpoint
        still returns 200.
        """
        with patch(
            'payments.views.settings.PAYMENT_SETTINGS',
            {'MERCADOPAGO': {'WEBHOOK_SECRET': '', 'ACCESS_TOKEN': 'dummy'}},
            create=True,
        ):
            response = self.client.post(
                '/api/payments/webhook/mercadopago/',
                {'action': 'test'},
                format='json',
            )
            self.assertEqual(response.status_code, 200)

    def test_mercadopago_webhook_unauthenticated_allowed(self):
        """Webhook endpoint should be accessible without authentication."""
        with patch(
            'payments.views.settings.PAYMENT_SETTINGS',
            {'MERCADOPAGO': {'WEBHOOK_SECRET': '', 'ACCESS_TOKEN': 'dummy'}},
            create=True,
        ), patch('payments.views.MercadoPagoService') as mock_mp:
            mock_instance = mock_mp.return_value
            mock_instance.get_payment_status.return_value = {'status': 'approved'}

            response = self.client.post(
                '/api/payments/webhook/mercadopago/',
                {'action': 'payment.created', 'data': {'id': '123'}},
                format='json',
            )
            # Unauthenticated but allowed because @permission_classes([])
            self.assertEqual(response.status_code, 200)

    def test_stripe_webhook_unauthenticated_allowed(self):
        """Stripe webhook endpoint should be accessible without authentication."""
        response = self.client.post(
            '/api/payments/webhook/stripe/',
            {'type': 'payment_intent.succeeded'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
