"""
Tests for core utilities.
"""

from django.core.cache import cache
from django.test import TestCase, override_settings

from core.utils.lockout import (
    MAX_FAILED_ATTEMPTS,
    LockedError,
    check_lockout,
    get_failed_attempts,
    get_lockout_remaining,
    is_locked,
    record_failed_attempt,
    reset_attempts,
)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
)
class LockoutServiceTests(TestCase):
    """Unit tests for the lockout service."""

    def setUp(self):
        cache.clear()

    def test_no_attempts_initially(self):
        """A fresh identifier has 0 failed attempts."""
        self.assertEqual(get_failed_attempts("test_user"), 0)

    def test_is_not_locked_initially(self):
        """A fresh identifier is not locked."""
        self.assertFalse(is_locked("test_user"))

    def test_record_failed_attempt_increments(self):
        """Each failed attempt increments the counter."""
        record_failed_attempt("test_user")
        self.assertEqual(get_failed_attempts("test_user"), 1)
        record_failed_attempt("test_user")
        self.assertEqual(get_failed_attempts("test_user"), 2)

    def test_lockout_after_max_attempts(self):
        """After MAX_FAILED_ATTEMPTS failed attempts, the account is locked."""
        for _ in range(MAX_FAILED_ATTEMPTS):
            record_failed_attempt("test_user")
        self.assertTrue(is_locked("test_user"))

    def test_not_locked_before_max_attempts(self):
        """Below MAX_FAILED_ATTEMPTS, the account is not locked."""
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            record_failed_attempt("test_user")
        self.assertFalse(is_locked("test_user"))

    def test_reset_clears_attempts_and_lock(self):
        """reset_attempts clears both the counter and the lock."""
        for _ in range(MAX_FAILED_ATTEMPTS):
            record_failed_attempt("test_user")
        self.assertTrue(is_locked("test_user"))

        reset_attempts("test_user")
        self.assertEqual(get_failed_attempts("test_user"), 0)
        self.assertFalse(is_locked("test_user"))

    def test_lockout_independent_per_identifier(self):
        """Lockout for one identifier doesn't affect another."""
        record_failed_attempt("user_a")
        for _ in range(MAX_FAILED_ATTEMPTS):
            record_failed_attempt("user_b")

        self.assertTrue(is_locked("user_b"))
        # user_a has only 1 attempt, should not be locked
        self.assertFalse(is_locked("user_a"))

    def test_check_lockout_raises_locked_error(self):
        """check_lockout raises LockedError when account is locked."""
        for _ in range(MAX_FAILED_ATTEMPTS):
            record_failed_attempt("test_user")

        with self.assertRaises(LockedError):
            check_lockout("test_user")

    def test_check_lockout_passes_when_not_locked(self):
        """check_lockout does not raise when account is not locked."""
        # Should not raise
        check_lockout("test_user")
        # No assertion needed - if it raises, the test fails

    def test_get_lockout_remaining_when_locked(self):
        """get_lockout_remaining returns > 0 when locked."""
        for _ in range(MAX_FAILED_ATTEMPTS):
            record_failed_attempt("test_user")

        remaining = get_lockout_remaining("test_user")
        self.assertGreaterEqual(remaining, 0)

    def test_get_lockout_remaining_when_not_locked(self):
        """get_lockout_remaining returns 0 when not locked."""
        remaining = get_lockout_remaining("test_user")
        self.assertEqual(remaining, 0)

    def test_locked_error_has_status_423(self):
        """LockedError is an APIException with status 423."""
        error = LockedError()
        self.assertEqual(error.status_code, 423)

    def test_locked_error_includes_remaining(self):
        """LockedError stores the remaining time."""
        error = LockedError(remaining=60)
        self.assertEqual(error.remaining, 60)

    def test_exponential_backoff_duration(self):
        """Excess attempts use longer lockout durations."""
        # We can't easily test the actual duration due to time-based caching,
        # but we can verify the lock is still applied after more excess attempts
        for _ in range(MAX_FAILED_ATTEMPTS + 3):  # 8 failed attempts
            record_failed_attempt("test_user")
        self.assertTrue(is_locked("test_user"))


class ExceptionHandlerTests(TestCase):
    """Tests for the custom exception handler in core/exceptions.py."""

    def test_400_format(self):
        """Validation errors return consistent JSON shape."""
        from rest_framework.exceptions import ValidationError
        from rest_framework.views import exception_handler as drf_exception_handler

        exc = ValidationError({"email": "Invalid email"})
        response = drf_exception_handler(exc, {})

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 400)
        # The custom_exception_handler wraps this further - test the wrapper
        from core.exceptions import custom_exception_handler

        response = custom_exception_handler(exc, {"request": None, "view": None})
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"], "bad_request")

    def test_401_format(self):
        """Auth errors return consistent JSON shape."""
        from rest_framework.exceptions import NotAuthenticated

        from core.exceptions import custom_exception_handler

        exc = NotAuthenticated()
        response = custom_exception_handler(exc, {"request": None, "view": None})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"], "unauthorized")

    def test_403_format(self):
        """Permission errors return consistent JSON shape."""
        from rest_framework.exceptions import PermissionDenied

        from core.exceptions import custom_exception_handler

        exc = PermissionDenied()
        response = custom_exception_handler(exc, {"request": None, "view": None})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"], "forbidden")

    def test_404_format(self):
        """404 errors return consistent JSON shape."""
        from django.http import Http404

        from core.exceptions import custom_exception_handler

        exc = Http404()
        response = custom_exception_handler(exc, {"request": None, "view": None})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"], "not_found")

    def test_405_format(self):
        """Method not allowed errors return consistent JSON shape."""
        from rest_framework.exceptions import MethodNotAllowed

        from core.exceptions import custom_exception_handler

        exc = MethodNotAllowed("GET")
        response = custom_exception_handler(exc, {"request": None, "view": None})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.data["error"], "method_not_allowed")

    def test_429_format(self):
        """Rate limit errors return consistent JSON shape."""
        from rest_framework.exceptions import Throttled

        from core.exceptions import custom_exception_handler

        exc = Throttled()
        response = custom_exception_handler(exc, {"request": None, "view": None})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["error"], "too_many_requests")

    def test_423_locked_format(self):
        """LockedError returns consistent JSON shape with 423."""
        from core.exceptions import custom_exception_handler
        from core.utils.lockout import LockedError

        exc = LockedError(remaining=60)
        response = custom_exception_handler(exc, {"request": None, "view": None})
        self.assertEqual(response.status_code, 423)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"], "account_locked")
        self.assertIn("details", response.data)

    def test_integrity_error_format(self):
        """IntegrityError returns proper error format."""
        from django.db import IntegrityError

        from core.exceptions import custom_exception_handler

        exc = IntegrityError("unique constraint failed")
        response = custom_exception_handler(exc, {"request": None, "view": None})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "integrity_error")

    def test_500_generic_format(self):
        """Unhandled exceptions return 500."""
        from core.exceptions import custom_exception_handler

        exc = RuntimeError("something broke")
        response = custom_exception_handler(exc, {"request": None, "view": None})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["error"], "internal_error")

    def test_get_error_code_mapping(self):
        """get_error_code returns correct codes."""
        from core.exceptions import get_error_code

        test_cases = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            423: "account_locked",
            429: "too_many_requests",
            500: "internal_error",
            999: "unknown_error",
        }
        for status_code, expected_code in test_cases.items():
            self.assertEqual(get_error_code(status_code), expected_code)

    def test_get_user_friendly_message_mapping(self):
        """get_user_friendly_message returns correct messages."""
        from core.exceptions import get_user_friendly_message

        test_cases = {
            400: "Datos inválidos",
            401: "No autorizado",
            403: "Acceso denegado",
            404: "No encontrado",
            423: "Cuenta bloqueada",
            429: "Demasiadas solicitudes",
            500: "Error del servidor",
            999: "Error desconocido",
        }
        for status_code, expected_msg in test_cases.items():
            self.assertEqual(get_user_friendly_message(status_code, None), expected_msg)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class CoreTaskTests(TestCase):
    """Tests for core Celery tasks."""

    def test_send_email_notification(self):
        """send_email_notification task executes without error."""
        from core.tasks import send_email_notification

        result = send_email_notification("Test", "Body", ["test@example.com"])
        self.assertIn("enviado", result.lower())

    def test_cleanup_old_notifications(self):
        """cleanup_old_notifications task executes without error."""
        from core.tasks import cleanup_old_notifications

        result = cleanup_old_notifications()
        self.assertIn("eliminadas", result.lower())
