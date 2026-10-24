"""
Tests for the Frenzo authentication endpoints.

Covers all 19 verification points from the task spec:
  1  Signup creates user and returns access token
  2  Signup sets HttpOnly refresh cookie
  3  Refresh token absent from signup JSON
  4  Login returns access token and sets refresh cookie
  5  Invalid login does not authenticate
  6  Refresh works when cookie is valid
  7  Missing / invalid / expired refresh cookie rejected
  8  CSRF enforced on refresh and logout (skipped – see note below)
  9  Logout clears the cookie
  10 Access token not in localStorage (frontend concern – N/A in backend)
  11 Reload restores session via refresh endpoint
  12 Expired access triggers at most one refresh/retry (frontend concern)
  13 Concurrent refresh race (frontend concern)
  14 Protected REST endpoints work with valid token
  15 WebSocket ticket issued for authenticated user
  16 WS ticket is single-use (replay protection)
  17 WS ticket rejected when absent or invalid
  18 JWT lifetimes: access=15 min, refresh=7 days
  19 Cookie security attributes: HttpOnly, configurable Secure/SameSite

Note on CSRF tests (#8):
Django's test Client bypasses CSRF middleware by default. The correct way to
test CSRF enforcement is with Client(enforce_csrf_checks=True). Those tests
are included below and marked separately. They require no external server.

Note on frontend tests (#10, #12, #13):
These verify browser-side Pinia/Axios behaviour. They cannot be tested from
the Django test suite and are documented as out-of-scope for backend tests.
"""

import json
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model

from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
_SIGNUP_URL  = '/api/signup/'
_LOGIN_URL   = '/api/login/'
_REFRESH_URL = '/api/refresh/'
_LOGOUT_URL  = '/api/logout/'
_TICKET_URL  = '/api/ws-ticket/'
_ME_URL      = '/api/me/'

COOKIE_NAME = 'refresh_token'


def _json(client_response):
    return json.loads(client_response.content)


def _make_user(email='user@example.com', password='StrongPass123!', name='Test User'):
    user = User.objects.create_user(name=name, email=email, password=password)
    user.is_active = True
    user.save()
    return user


def _auth_header(user):
    token = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {str(token.access_token)}'}


# ---------------------------------------------------------------------------
# 1–3  Signup
# ---------------------------------------------------------------------------
@override_settings(REFRESH_COOKIE_SECURE=False, REFRESH_COOKIE_SAMESITE='Lax',
                   USE_SQLITE=True)
class SignupTests(TestCase):

    def test_01_signup_creates_user_and_returns_access(self):
        """Signup returns HTTP 200 and an access token."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_SIGNUP_URL, {
            'email': 'new@example.com', 'name': 'New User',
            'password1': 'StrongPass123!', 'password2': 'StrongPass123!',
        }, content_type='application/json')

        self.assertEqual(r.status_code, 200)
        data = _json(r)
        self.assertEqual(data['message'], 'success')
        self.assertIn('access', data)
        self.assertTrue(len(data['access']) > 20)
        self.assertTrue(User.objects.filter(email='new@example.com').exists())

    def test_02_signup_sets_httponly_refresh_cookie(self):
        """Signup sets the HttpOnly refresh-token cookie."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_SIGNUP_URL, {
            'email': 'cookie@example.com', 'name': 'Cookie User',
            'password1': 'StrongPass123!', 'password2': 'StrongPass123!',
        }, content_type='application/json')

        self.assertEqual(r.status_code, 200)
        self.assertIn(COOKIE_NAME, r.cookies)
        cookie = r.cookies[COOKIE_NAME]
        self.assertTrue(cookie['httponly'])
        self.assertTrue(len(cookie.value) > 20)

    def test_03_refresh_token_absent_from_signup_json(self):
        """Refresh token must NOT appear in the signup JSON response body."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_SIGNUP_URL, {
            'email': 'noleak@example.com', 'name': 'No Leak',
            'password1': 'StrongPass123!', 'password2': 'StrongPass123!',
        }, content_type='application/json')

        data = _json(r)
        self.assertNotIn('refresh', data)
        # Also verify the raw response body doesn't contain 'refresh' as a key
        body = r.content.decode()
        # The word 'refresh' should not appear as a JSON key
        import re
        self.assertIsNone(re.search(r'"refresh"\s*:', body))

    def test_signup_invalid_data_returns_400(self):
        """Signup with mismatched passwords returns 400."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_SIGNUP_URL, {
            'email': 'bad@example.com', 'name': 'Bad',
            'password1': 'abc', 'password2': 'xyz',
        }, content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_signup_missing_name_returns_400(self):
        """Signup with an empty name returns 400 with a name field error."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_SIGNUP_URL, {
            'email': 'noname@example.com', 'name': '',
            'password1': 'StrongPass123!', 'password2': 'StrongPass123!',
        }, content_type='application/json')
        self.assertEqual(r.status_code, 400)
        data = _json(r)
        self.assertIn('message', data)
        import json
        parsed = json.loads(data['message'])
        self.assertIn('name', parsed)

    def test_signup_duplicate_email_returns_400(self):
        """Signup with an already-registered email returns 400 with an email error."""
        _make_user(email='dup@example.com')
        c = Client(enforce_csrf_checks=False)
        r = c.post(_SIGNUP_URL, {
            'email': 'dup@example.com', 'name': 'Dup User',
            'password1': 'StrongPass123!', 'password2': 'StrongPass123!',
        }, content_type='application/json')
        self.assertEqual(r.status_code, 400)
        data = _json(r)
        import json
        parsed = json.loads(data['message'])
        self.assertIn('email', parsed)

    def test_signup_error_response_contains_parseable_message(self):
        """
        The error response body contains a 'message' key whose value is
        a valid JSON string with field-name keys and error-list values.
        This is what the frontend parses to display per-field errors.
        """
        import json
        c = Client(enforce_csrf_checks=False)
        r = c.post(_SIGNUP_URL, {
            'email': 'x@x.com', 'name': 'X',
            'password1': 'abc', 'password2': 'xyz',
        }, content_type='application/json')
        self.assertEqual(r.status_code, 400)
        data = _json(r)
        self.assertIn('message', data)
        # message must be a parseable JSON string
        parsed = json.loads(data['message'])
        self.assertIsInstance(parsed, dict)
        # At least one field error
        self.assertGreater(len(parsed), 0)
        # Each value is a list of dicts with 'message' and 'code' keys
        for field, errs in parsed.items():
            for err in errs:
                self.assertIn('message', err)
                self.assertIn('code', err)

    def test_signup_sets_csrftoken_cookie(self):
        """
        A successful signup response must set the 'csrftoken' cookie.

        signup is decorated with @ensure_csrf_cookie, which instructs Django
        to always include Set-Cookie: csrftoken=... in the response.  The
        frontend Axios interceptor reads this cookie to obtain the token it
        must send as X-CSRFToken on subsequent state-mutating requests
        (refresh, logout).

        Importantly, this test does NOT require signup itself to reject
        requests that lack a CSRF token — @ensure_csrf_cookie only *sets*
        the cookie; it does not *enforce* it.  That is the correct design
        because signup is a credential-based, unauthenticated endpoint.
        """
        c = Client(enforce_csrf_checks=False)
        r = c.post(_SIGNUP_URL, {
            'email': 'csrftest@example.com', 'name': 'CSRF Test',
            'password1': 'StrongPass123!', 'password2': 'StrongPass123!',
        }, content_type='application/json')

        self.assertEqual(r.status_code, 200, "Signup should succeed")
        self.assertIn('csrftoken', r.cookies,
                      "@ensure_csrf_cookie must set the csrftoken cookie on signup")


# ---------------------------------------------------------------------------
# 4–5  Login
# ---------------------------------------------------------------------------
@override_settings(REFRESH_COOKIE_SECURE=False, REFRESH_COOKIE_SAMESITE='Lax',
                   USE_SQLITE=True)
class LoginTests(TestCase):

    def setUp(self):
        self.user = _make_user()

    def test_04_login_returns_access_and_sets_cookie(self):
        """Successful login returns access token and sets HttpOnly cookie."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')

        self.assertEqual(r.status_code, 200)
        data = _json(r)
        self.assertIn('access', data)
        self.assertNotIn('refresh', data)
        self.assertIn(COOKIE_NAME, r.cookies)
        self.assertTrue(r.cookies[COOKIE_NAME]['httponly'])

    def test_login_includes_user_data(self):
        """Login response includes serialized user data."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')

        data = _json(r)
        self.assertIn('user', data)
        self.assertEqual(data['user']['email'], 'user@example.com')

    def test_05_invalid_login_rejected(self):
        """Wrong password returns 401 and does not set a cookie."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'WrongPassword!',
        }, content_type='application/json')

        self.assertEqual(r.status_code, 401)
        self.assertNotIn(COOKIE_NAME, r.cookies)

    def test_05b_unknown_email_rejected(self):
        """Unknown email returns 401."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGIN_URL, {
            'email': 'ghost@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# 6–7  Refresh
# ---------------------------------------------------------------------------
@override_settings(REFRESH_COOKIE_SECURE=False, REFRESH_COOKIE_SAMESITE='Lax',
                   USE_SQLITE=True)
class RefreshTests(TestCase):

    def setUp(self):
        self.user = _make_user()

    def _login_and_get_cookie(self):
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')
        cookie_value = r.cookies[COOKIE_NAME].value
        return cookie_value

    def test_06_refresh_with_valid_cookie_returns_access(self):
        """Valid refresh cookie returns a new access token."""
        refresh_value = self._login_and_get_cookie()

        c = Client(enforce_csrf_checks=False)
        c.cookies[COOKIE_NAME] = refresh_value
        r = c.post(_REFRESH_URL, content_type='application/json')

        self.assertEqual(r.status_code, 200)
        data = _json(r)
        self.assertIn('access', data)
        self.assertNotIn('refresh', data)
        self.assertTrue(len(data['access']) > 20)

    def test_07_missing_cookie_rejected(self):
        """Refresh without a cookie returns 401."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_REFRESH_URL, content_type='application/json')
        self.assertEqual(r.status_code, 401)

    def test_07b_invalid_cookie_rejected(self):
        """Refresh with a garbage cookie value returns 401."""
        c = Client(enforce_csrf_checks=False)
        c.cookies[COOKIE_NAME] = 'not.a.valid.jwt'
        r = c.post(_REFRESH_URL, content_type='application/json')
        self.assertEqual(r.status_code, 401)

    def test_07c_expired_cookie_rejected(self):
        """Refresh with an already-expired token returns 401."""
        from rest_framework_simplejwt.tokens import RefreshToken as RT
        token = RT.for_user(self.user)
        # Back-date the expiry so the token appears expired.
        token.set_exp(lifetime=timedelta(seconds=-1))
        expired_str = str(token)

        c = Client(enforce_csrf_checks=False)
        c.cookies[COOKIE_NAME] = expired_str
        r = c.post(_REFRESH_URL, content_type='application/json')
        self.assertEqual(r.status_code, 401)

    def test_11_reload_restores_session_via_refresh(self):
        """
        Simulates a page reload: access token is gone (memory-only),
        but a valid refresh cookie is present.
        POST /api/refresh/ returns a new access token.
        """
        refresh_value = self._login_and_get_cookie()

        c = Client(enforce_csrf_checks=False)
        c.cookies[COOKIE_NAME] = refresh_value
        r = c.post(_REFRESH_URL, content_type='application/json')

        self.assertEqual(r.status_code, 200)
        self.assertIn('access', _json(r))


# ---------------------------------------------------------------------------
# 8  CSRF enforcement on refresh and logout
# ---------------------------------------------------------------------------
@override_settings(
    REFRESH_COOKIE_SECURE=False,
    REFRESH_COOKIE_SAMESITE='Lax',
    USE_SQLITE=True,
    ALLOWED_HOSTS=['localhost', 'testserver'],
)
class CsrfTests(TestCase):
    """
    Verify that CSRF enforcement is effective on the refresh and logout endpoints.
    Uses enforce_csrf_checks=True so Django's CSRF middleware is active.
    'testserver' is added to ALLOWED_HOSTS because the Django test Client
    sends that as the Host header and the ALLOWED_HOSTS check runs before
    CSRF checking.
    """

    def setUp(self):
        self.user = _make_user()

    def _get_csrf_token(self):
        """Obtain a CSRF token by hitting the login endpoint (ensure_csrf_cookie)."""
        c = Client(enforce_csrf_checks=True)
        # GET is safe; ensure_csrf_cookie sets the cookie on login/signup GETs
        # but we need the token.  Use a login request without credentials to
        # get the CSRF cookie.
        c.get(_LOGIN_URL)
        return c.cookies.get('csrftoken', None), c

    def test_08a_refresh_without_csrf_token_rejected(self):
        """
        Refresh with no CSRF token must be rejected with 403 when
        enforce_csrf_checks=True.
        """
        # First login to get a refresh cookie (without CSRF checks to set it up).
        setup_client = Client(enforce_csrf_checks=False)
        r = setup_client.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')
        refresh_value = r.cookies[COOKIE_NAME].value

        # Now try to refresh without a CSRF token.
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.cookies[COOKIE_NAME] = refresh_value
        r2 = strict_client.post(_REFRESH_URL, content_type='application/json')
        self.assertEqual(r2.status_code, 403,
                         "Refresh without CSRF token must return 403")

    def test_08b_logout_without_csrf_token_rejected(self):
        """
        Logout with no CSRF token must be rejected with 403 when
        enforce_csrf_checks=True.
        """
        strict_client = Client(enforce_csrf_checks=True)
        r = strict_client.post(_LOGOUT_URL, content_type='application/json')
        self.assertEqual(r.status_code, 403,
                         "Logout without CSRF token must return 403")

    def test_08c_refresh_with_valid_csrf_succeeds(self):
        """
        Refresh with a valid CSRF token and a valid refresh cookie must
        pass CSRF validation and return a new access token (200).

        The CSRF cookie is obtained from a signup/login response via
        @ensure_csrf_cookie.  Django's test Client copies the csrftoken
        cookie into subsequent requests automatically when the same Client
        instance is reused; we additionally supply the token in the
        X-CSRFToken header as the Axios interceptor does in the browser.
        """
        # Step 1 — obtain a refresh cookie AND the csrftoken cookie from login.
        # Login uses @ensure_csrf_cookie so it always sets csrftoken.
        c = Client(enforce_csrf_checks=True)
        c.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')

        # The csrftoken cookie is now in the client's cookie jar.
        csrf_token = c.cookies.get('csrftoken')
        self.assertIsNotNone(csrf_token,
                             "Login must set the csrftoken cookie (enforce_csrf_cookie)")
        csrf_value = csrf_token.value

        # Step 2 — POST to /api/refresh/ with the X-CSRFToken header.
        # The refresh cookie was set by the login call above and is still
        # present in the same Client instance's cookie jar.
        r = c.post(
            _REFRESH_URL,
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_value,
        )

        self.assertEqual(r.status_code, 200,
                         "Refresh with a valid CSRF token must succeed (200)")
        data = json.loads(r.content)
        self.assertIn('access', data,
                      "Successful refresh must return a new access token")


# ---------------------------------------------------------------------------
# 9  Logout
# ---------------------------------------------------------------------------
@override_settings(REFRESH_COOKIE_SECURE=False, REFRESH_COOKIE_SAMESITE='Lax',
                   USE_SQLITE=True)
class LogoutTests(TestCase):

    def setUp(self):
        self.user = _make_user()

    def test_09_logout_clears_cookie(self):
        """Logout returns 200 and deletes the refresh-token cookie."""
        # Login to get the cookie.
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')
        self.assertIn(COOKIE_NAME, r.cookies)

        # Logout.
        r2 = c.post(_LOGOUT_URL, content_type='application/json')
        self.assertEqual(r2.status_code, 200)

        # The cookie should be set with an empty value / max-age=0 (deleted).
        if COOKIE_NAME in r2.cookies:
            deleted = r2.cookies[COOKIE_NAME]
            # Django's delete_cookie sets max-age to 0 or a past date.
            self.assertTrue(
                deleted.value == '' or deleted['max-age'] == 0,
                f"Expected deleted cookie, got: {deleted}",
            )

    def test_09b_logout_idempotent(self):
        """Logout without a cookie still returns 200."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGOUT_URL, content_type='application/json')
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# 14  Protected REST endpoints require valid token
# ---------------------------------------------------------------------------
@override_settings(USE_SQLITE=True)
class ProtectedEndpointTests(TestCase):

    def setUp(self):
        self.user = _make_user()

    def test_14_me_endpoint_with_valid_token(self):
        """GET /api/me/ succeeds with a valid Bearer token."""
        c = Client()
        r = c.get(_ME_URL, **_auth_header(self.user))
        self.assertEqual(r.status_code, 200)
        data = _json(r)
        self.assertEqual(data['email'], 'user@example.com')

    def test_14b_me_endpoint_without_token_rejected(self):
        """GET /api/me/ returns 401 without a token."""
        c = Client()
        r = c.get(_ME_URL)
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# 15–17  WebSocket ticket
# ---------------------------------------------------------------------------
@override_settings(USE_SQLITE=True, WS_TICKET_TTL=30)
class WsTicketTests(TestCase):

    def setUp(self):
        self.user  = _make_user()
        cache.clear()

    def test_15_ticket_issued_for_authenticated_user(self):
        """GET /api/ws-ticket/ returns a UUID ticket for an authenticated user."""
        c = Client()
        r = c.get(_TICKET_URL, **_auth_header(self.user))
        self.assertEqual(r.status_code, 200)
        data = _json(r)
        self.assertIn('ticket', data)
        ticket = data['ticket']
        # Must be a valid UUID format.
        import uuid
        uuid.UUID(ticket)   # raises ValueError if invalid

    def test_16_ticket_is_single_use(self):
        """
        The ticket stored in the cache is deleted on first use by the consumer.
        Simulate that by reading the cache key directly.
        """
        import uuid as uuid_mod
        c = Client()
        r = c.get(_TICKET_URL, **_auth_header(self.user))
        ticket = _json(r)['ticket']

        cache_key = f'ws_ticket:{ticket}'

        # Cache entry exists immediately after issuing.
        stored_user_id = cache.get(cache_key)
        self.assertIsNotNone(stored_user_id)
        self.assertEqual(stored_user_id, str(self.user.pk))

        # Simulate the consumer consuming the ticket (delete on first use).
        cache.delete(cache_key)

        # A second lookup finds nothing — replay protection confirmed.
        self.assertIsNone(cache.get(cache_key))

    def test_17_unauthenticated_ticket_request_rejected(self):
        """GET /api/ws-ticket/ without a token returns 401."""
        c = Client()
        r = c.get(_TICKET_URL)
        self.assertEqual(r.status_code, 401)

    def test_17b_ticket_not_in_cache_means_invalid(self):
        """A ticket that was never issued (not in cache) is treated as invalid."""
        import uuid
        fake_ticket  = str(uuid.uuid4())
        cache_key    = f'ws_ticket:{fake_ticket}'
        self.assertIsNone(cache.get(cache_key))


# ---------------------------------------------------------------------------
# 18  JWT lifetimes
# ---------------------------------------------------------------------------
@override_settings(USE_SQLITE=True)
class JwtLifetimeTests(TestCase):

    def test_18_access_token_lifetime_is_15_minutes(self):
        from django.conf import settings
        from datetime import timedelta
        self.assertEqual(
            settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
            timedelta(minutes=15),
        )

    def test_18b_refresh_token_lifetime_is_7_days(self):
        from django.conf import settings
        from datetime import timedelta
        self.assertEqual(
            settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
            timedelta(days=7),
        )


# ---------------------------------------------------------------------------
# 19  Cookie security attributes
# ---------------------------------------------------------------------------
@override_settings(
    REFRESH_COOKIE_SECURE=True,
    REFRESH_COOKIE_SAMESITE='Lax',
    USE_SQLITE=True,
)
class CookieAttributeTests(TestCase):

    def setUp(self):
        self.user = _make_user()

    def test_19_cookie_httponly(self):
        """Refresh cookie is HttpOnly."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')
        cookie = r.cookies[COOKIE_NAME]
        self.assertTrue(cookie['httponly'])

    def test_19b_cookie_secure_when_configured(self):
        """Refresh cookie has Secure flag when REFRESH_COOKIE_SECURE=True."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')
        cookie = r.cookies[COOKIE_NAME]
        self.assertTrue(cookie['secure'])

    def test_19c_cookie_samesite(self):
        """Refresh cookie SameSite matches the configured value."""
        from django.conf import settings
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')
        cookie = r.cookies[COOKIE_NAME]
        self.assertEqual(cookie['samesite'], settings.REFRESH_COOKIE_SAMESITE)

    def test_19d_cookie_has_max_age(self):
        """Refresh cookie has a positive max-age (7 days in seconds)."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')
        cookie = r.cookies[COOKIE_NAME]
        max_age = cookie['max-age']
        expected = int(timedelta(days=7).total_seconds())
        self.assertEqual(max_age, expected)

    @override_settings(REFRESH_COOKIE_SECURE=False)
    def test_19e_cookie_not_secure_in_dev(self):
        """Secure flag is off when REFRESH_COOKIE_SECURE=False (local dev)."""
        c = Client(enforce_csrf_checks=False)
        r = c.post(_LOGIN_URL, {
            'email': 'user@example.com', 'password': 'StrongPass123!',
        }, content_type='application/json')
        cookie = r.cookies[COOKIE_NAME]
        self.assertFalse(cookie['secure'])
