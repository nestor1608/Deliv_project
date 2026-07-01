"""
Comprehensive API tests for the Notifications app.
Covers NotificationViewSet, UserDeviceViewSet, send_bulk_notification,
mark_as_read standalone view, and test_notification action.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django.utils import timezone
from tests.factories import APITestCase
from rest_framework import status

from tests.factories import (
    UserFactory,
    NotificationTypeFactory,
    NotificationFactory,
    UserDeviceFactory,
)
from notifications.models import Notification, UserDevice

User = get_user_model()


@override_settings(DEBUG=True)
class NotificationViewSetTests(APITestCase):
    """Tests for the NotificationViewSet (/api/notifications/notifications/)."""

    def setUp(self):
        self.user = UserFactory(role='customer')
        self.other_user = UserFactory(role='customer')
        self.admin_user = UserFactory(role='admin', is_staff=True)
        self.notification_type = NotificationTypeFactory()

    # --- GET list ---

    def test_list_notifications_empty(self):
        """GET /api/notifications/notifications/ returns empty list when user has no notifications."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_list_notifications_with_data(self):
        """GET /api/notifications/notifications/ returns only the authenticated user's notifications."""
        NotificationFactory.create_batch(3, user=self.user, notification_type=self.notification_type)
        NotificationFactory.create_batch(2, user=self.other_user, notification_type=self.notification_type)
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)

    def test_list_notifications_other_user_notifications_not_visible(self):
        """Notifications belonging to other users must not appear in the list."""
        NotificationFactory(user=self.other_user, notification_type=self.notification_type)
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/notifications/')
        self.assertEqual(response.data['count'], 0)

    def test_list_notifications_unauthenticated(self):
        """Unauthenticated request returns 401."""
        response = self.client.get('/api/notifications/notifications/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- POST create (admin only) ---

    @patch('notifications.signals.send_push_notification.delay')
    def test_create_notification_admin_success(self, mock_delay):
        """POST /api/notifications/notifications/ – admin can create a notification."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'user_id': self.user.id,
            'notification_type_id': self.notification_type.id,
            'title': 'Test title',
            'body': 'Test body',
        }
        response = self.client.post('/api/notifications/notifications/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Notification.objects.first().user, self.user)

    def test_create_notification_non_admin_forbidden(self):
        """POST /api/notifications/notifications/ – non-admin gets 403."""
        self.client.force_authenticate(user=self.user)
        data = {
            'user_id': self.user.id,
            'notification_type_id': self.notification_type.id,
            'title': 'Test',
            'body': 'Body',
        }
        response = self.client.post('/api/notifications/notifications/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_notification_unauthenticated(self):
        """POST /api/notifications/notifications/ – unauthenticated gets 401."""
        data = {
            'user_id': 1,
            'notification_type_id': 1,
            'title': 'Test',
            'body': 'Body',
        }
        response = self.client.post('/api/notifications/notifications/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_notification_invalid_user_id_400(self):
        """POST with non-existent user_id returns 400."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'user_id': 99999,
            'notification_type_id': self.notification_type.id,
            'title': 'Test',
            'body': 'Body',
        }
        response = self.client.post('/api/notifications/notifications/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_notification_invalid_type_id_400(self):
        """POST with non-existent notification_type_id returns 400."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'user_id': self.user.id,
            'notification_type_id': 99999,
            'title': 'Test',
            'body': 'Body',
        }
        response = self.client.post('/api/notifications/notifications/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- GET retrieve ---

    def test_retrieve_own_notification(self):
        """GET /api/notifications/notifications/<pk>/ returns own notification."""
        notification = NotificationFactory(user=self.user, notification_type=self.notification_type)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/notifications/notifications/{notification.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], notification.title)

    def test_retrieve_other_notification_404(self):
        """GET /api/notifications/notifications/<pk>/ returns 404 for another user's notification."""
        notification = NotificationFactory(user=self.other_user, notification_type=self.notification_type)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/notifications/notifications/{notification.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_notification_unauthenticated(self):
        """Unauthenticated retrieve returns 401."""
        notification = NotificationFactory(user=self.user, notification_type=self.notification_type)
        response = self.client.get(f'/api/notifications/notifications/{notification.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- PATCH mark_as_read ---

    def test_mark_as_read_success(self):
        """PATCH .../mark_as_read/ marks a sent notification as read."""
        notification = NotificationFactory(
            user=self.user, notification_type=self.notification_type, status='sent'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            f'/api/notifications/notifications/{notification.id}/mark_as_read/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'read')
        self.assertIsNotNone(notification.read_at)

    def test_mark_as_read_already_read_does_not_change_read_at(self):
        """Marking an already-read notification still returns 200."""
        notification = NotificationFactory(
            user=self.user, notification_type=self.notification_type, status='read',
            read_at=timezone.now()
        )
        original_read_at = notification.read_at
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            f'/api/notifications/notifications/{notification.id}/mark_as_read/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertEqual(notification.read_at, original_read_at)

    def test_mark_as_read_other_user_404(self):
        """mark_as_read on another user's notification returns 404."""
        notification = NotificationFactory(
            user=self.other_user, notification_type=self.notification_type, status='sent'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            f'/api/notifications/notifications/{notification.id}/mark_as_read/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_as_read_nonexistent_404(self):
        """mark_as_read on a non-existent notification returns 404."""
        self.client.force_authenticate(user=self.user)
        response = self.client.patch('/api/notifications/notifications/99999/mark_as_read/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_as_read_unauthenticated(self):
        """Unauthenticated mark_as_read returns 401."""
        notification = NotificationFactory(user=self.user, notification_type=self.notification_type)
        response = self.client.patch(
            f'/api/notifications/notifications/{notification.id}/mark_as_read/'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- PATCH mark_all_read ---

    def test_mark_all_read_success(self):
        """PATCH .../mark_all_read/ marks all unread notifications as read."""
        NotificationFactory.create_batch(
            3, user=self.user, notification_type=self.notification_type, status='sent'
        )
        NotificationFactory(
            user=self.user, notification_type=self.notification_type, status='read'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.patch('/api/notifications/notifications/mark_all_read/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Notification.objects.filter(user=self.user, status='read').count(), 4
        )

    def test_mark_all_read_when_none_unread(self):
        """mark_all_read with no unread notifications returns 200 with count 0."""
        NotificationFactory(
            user=self.user, notification_type=self.notification_type, status='read'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.patch('/api/notifications/notifications/mark_all_read/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('0 notificaciones', response.data['message'])

    # --- GET unread_count ---

    def test_unread_count_correct(self):
        """GET .../unread_count/ returns the correct count of unread notifications."""
        NotificationFactory.create_batch(
            5, user=self.user, notification_type=self.notification_type, status='sent'
        )
        NotificationFactory(
            user=self.user, notification_type=self.notification_type, status='read'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/notifications/unread_count/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 5)

    def test_unread_count_zero(self):
        """unread_count returns 0 when all notifications are read."""
        NotificationFactory(
            user=self.user, notification_type=self.notification_type, status='read'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/notifications/unread_count/')
        self.assertEqual(response.data['unread_count'], 0)

    def test_unread_count_empty(self):
        """unread_count returns 0 when user has no notifications."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/notifications/unread_count/')
        self.assertEqual(response.data['unread_count'], 0)

    # --- DELETE clear_old ---

    def test_clear_old_deletes_old_read_notifications(self):
        """DELETE .../clear_old/ removes read notifications older than 30 days."""
        cutoff = timezone.now() - timedelta(days=31)
        old = NotificationFactory(
            user=self.user, notification_type=self.notification_type, status='read'
        )
        Notification.objects.filter(id=old.id).update(read_at=cutoff)

        recent = NotificationFactory(
            user=self.user, notification_type=self.notification_type, status='read'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.delete('/api/notifications/notifications/clear_old/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Notification.objects.filter(id=old.id).exists())
        self.assertTrue(Notification.objects.filter(id=recent.id).exists())

    def test_clear_old_does_not_delete_unread(self):
        """Unread notifications are not removed by clear_old."""
        cutoff = timezone.now() - timedelta(days=31)
        unread = NotificationFactory(
            user=self.user, notification_type=self.notification_type, status='sent'
        )
        Notification.objects.filter(id=unread.id).update(created_at=cutoff)
        self.client.force_authenticate(user=self.user)
        self.client.delete('/api/notifications/notifications/clear_old/')
        self.assertTrue(Notification.objects.filter(id=unread.id).exists())

    def test_clear_old_no_notifications(self):
        """clear_old returns 200 when there are no old notifications."""
        self.client.force_authenticate(user=self.user)
        response = self.client.delete('/api/notifications/notifications/clear_old/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@override_settings(DEBUG=True)
class UserDeviceViewSetTests(APITestCase):
    """Tests for the UserDeviceViewSet (/api/notifications/devices/)."""

    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()

    # --- GET list ---

    def test_list_devices_empty(self):
        """GET /api/notifications/devices/ returns empty list for user with no devices."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/devices/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_list_devices_with_data(self):
        """GET /api/notifications/devices/ returns only the user's own devices."""
        UserDeviceFactory.create_batch(2, user=self.user)
        UserDeviceFactory(user=self.other_user)
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/devices/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_list_devices_unauthenticated(self):
        """Unauthenticated device list returns 401."""
        response = self.client.get('/api/notifications/devices/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- POST create ---

    def test_register_device_success(self):
        """POST /api/notifications/devices/ registers a new device with valid data."""
        self.client.force_authenticate(user=self.user)
        data = {
            'fcm_token': 'valid_token_1234567890',
            'platform': 'android',
            'device_id': 'device_001',
            'app_version': '1.0.0',
        }
        response = self.client.post('/api/notifications/devices/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserDevice.objects.filter(user=self.user).count(), 1)
        self.assertEqual(UserDevice.objects.first().fcm_token, 'valid_token_1234567890')

    def test_register_device_missing_fcm_token_400(self):
        """POST without fcm_token returns 400."""
        self.client.force_authenticate(user=self.user)
        data = {'platform': 'ios'}
        response = self.client.post('/api/notifications/devices/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_device_short_token_400(self):
        """POST with an fcm_token shorter than 10 characters returns 400."""
        self.client.force_authenticate(user=self.user)
        data = {
            'fcm_token': 'short',
            'platform': 'android',
        }
        response = self.client.post('/api/notifications/devices/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_device_unauthenticated(self):
        """Unauthenticated device registration returns 401."""
        data = {
            'fcm_token': 'valid_token_1234567890',
            'platform': 'android',
        }
        response = self.client.post('/api/notifications/devices/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- PATCH toggle_active ---

    def test_toggle_active_toggles(self):
        """PATCH .../toggle_active/ flips the is_active flag on the device."""
        device = UserDeviceFactory(user=self.user, is_active=True)
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            f'/api/notifications/devices/{device.id}/toggle_active/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device.refresh_from_db()
        self.assertFalse(device.is_active)

        # Toggle again
        response = self.client.patch(
            f'/api/notifications/devices/{device.id}/toggle_active/'
        )
        device.refresh_from_db()
        self.assertTrue(device.is_active)

    def test_toggle_active_other_user_404(self):
        """Toggle on another user's device returns 404."""
        device = UserDeviceFactory(user=self.other_user)
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            f'/api/notifications/devices/{device.id}/toggle_active/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_toggle_active_nonexistent_404(self):
        """Toggle on a non-existent device returns 404."""
        self.client.force_authenticate(user=self.user)
        response = self.client.patch('/api/notifications/devices/99999/toggle_active/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_toggle_active_unauthenticated(self):
        """Unauthenticated toggle_active returns 401."""
        device = UserDeviceFactory(user=self.user)
        response = self.client.patch(
            f'/api/notifications/devices/{device.id}/toggle_active/'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- POST test_notification ---

    @patch('notifications.views.FCMService')
    def test_test_notification_success(self, mock_fcm_service):
        """POST .../test_notification/ returns success when FCMService returns True."""
        mock_instance = mock_fcm_service.return_value
        mock_instance.send_notification.return_value = True

        device = UserDeviceFactory(user=self.user)
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f'/api/notifications/devices/{device.id}/test_notification/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('success', response.data)
        mock_instance.send_notification.assert_called_once()

    @patch('notifications.views.FCMService')
    def test_test_notification_other_user_404(self, mock_fcm_service):
        """Test notification on another user's device returns 404."""
        device = UserDeviceFactory(user=self.other_user)
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f'/api/notifications/devices/{device.id}/test_notification/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mock_fcm_service.assert_not_called()

    def test_test_notification_unauthenticated(self):
        """Unauthenticated test_notification returns 401."""
        device = UserDeviceFactory(user=self.user)
        response = self.client.post(
            f'/api/notifications/devices/{device.id}/test_notification/'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(DEBUG=True)
@patch('notifications.views.send_push_notification.delay')
class SendBulkNotificationTests(APITestCase):
    """Tests for the send_bulk_notification endpoint (/api/notifications/send-bulk/)."""

    def setUp(self):
        self.admin_user = UserFactory(role='admin', is_staff=True)
        self.non_admin = UserFactory(role='customer')
        UserFactory.create_batch(3, role='customer')  # target users

    def test_send_bulk_admin_success(self, mock_delay):
        """POST /api/notifications/send-bulk/ – admin can send bulk notifications."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'title': 'Bulk title',
            'body': 'Bulk body',
            'user_roles': ['customer'],
        }
        response = self.client.post('/api/notifications/send-bulk/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 4 customer users: self.non_admin + 3 batch customers
        self.assertEqual(response.data['success_count'], 4)

    def test_send_bulk_non_admin_forbidden(self, mock_delay):
        """POST /api/notifications/send-bulk/ – non-admin gets 403."""
        self.client.force_authenticate(user=self.non_admin)
        data = {
            'title': 'Bulk',
            'body': 'Body',
            'user_roles': ['customer'],
        }
        response = self.client.post('/api/notifications/send-bulk/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_send_bulk_with_user_ids(self, mock_delay):
        """Bulk notification with specific user_ids works."""
        self.client.force_authenticate(user=self.admin_user)
        target = UserFactory()
        data = {
            'title': 'Specific',
            'body': 'To one user',
            'user_ids': [target.id],
        }
        response = self.client.post('/api/notifications/send-bulk/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['success_count'], 1)

    def test_send_bulk_no_roles_or_ids_400(self, mock_delay):
        """Bulk without user_roles or user_ids returns 400."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'title': 'Bulk',
            'body': 'Body',
        }
        response = self.client.post('/api/notifications/send-bulk/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_bulk_no_matching_users_400(self, mock_delay):
        """Bulk with role criteria that matches no users returns 400."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'title': 'Bulk',
            'body': 'Body',
            'user_roles': ['delivery'],  # no delivery users exist
        }
        response = self.client.post('/api/notifications/send-bulk/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_bulk_unauthenticated(self, mock_delay):
        """Unauthenticated bulk request returns 401."""
        data = {
            'title': 'Bulk',
            'body': 'Body',
            'user_roles': ['customer'],
        }
        response = self.client.post('/api/notifications/send-bulk/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(DEBUG=True)
class MarkAsReadStandaloneTests(APITestCase):
    """Tests for the mark_as_read function-based view (/api/notifications/mark-read/<id>/)."""

    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.notification_type = NotificationTypeFactory()

    def test_mark_as_read_by_id_success(self):
        """PATCH /api/notifications/mark-read/<id>/ marks the notification as read for the owner."""
        notification = NotificationFactory(
            user=self.user, notification_type=self.notification_type, status='sent'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(f'/api/notifications/mark-read/{notification.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'read')
        self.assertIsNotNone(notification.read_at)

    def test_mark_as_read_by_id_other_user_404(self):
        """Marking another user's notification returns 404."""
        notification = NotificationFactory(
            user=self.other_user, notification_type=self.notification_type, status='sent'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(f'/api/notifications/mark-read/{notification.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_as_read_by_id_nonexistent_404(self):
        """Marking a non-existent notification returns 404."""
        self.client.force_authenticate(user=self.user)
        response = self.client.patch('/api/notifications/mark-read/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_as_read_by_id_already_read(self):
        """Marking an already-read notification returns 200 with updated data."""
        notification = NotificationFactory(
            user=self.user, notification_type=self.notification_type, status='read',
            read_at=timezone.now()
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(f'/api/notifications/mark-read/{notification.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_mark_as_read_by_id_unauthenticated(self):
        """Unauthenticated request returns 401."""
        notification = NotificationFactory(user=self.user, notification_type=self.notification_type)
        response = self.client.patch(f'/api/notifications/mark-read/{notification.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
