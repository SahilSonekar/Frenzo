"""
Account API endpoints.

Authentication flow
-------------------
POST /api/signup/      Register → access token in JSON + refresh cookie
POST /api/login/       Login    → access token in JSON + refresh cookie
POST /api/refresh/     Rotate   → new access token from cookie (no body needed)
POST /api/logout/      Clear    → expires the refresh cookie
GET  /api/ws-ticket/   Ticket   → short-lived WS ticket from valid access token

Refresh token storage
---------------------
The refresh token is stored exclusively as an HttpOnly cookie named
'refresh_token'.  It is NEVER included in any JSON response body.
JavaScript cannot read it.

CSRF protection
---------------
The refresh and logout endpoints do not use JWT authentication (they read the
cookie directly), so DRF's default CSRF-exempt behaviour for @api_view would
leave them unprotected.  They are explicitly wrapped with Django's
@csrf_protect to require a valid CSRF token.

The login endpoint is decorated with @ensure_csrf_cookie so the browser
receives the CSRF cookie on the first visit even before the user logs in.

Axios is configured on the frontend to:
  1. Send credentials (cookies) with every request.
  2. Read the CSRF token from the 'csrftoken' cookie and send it in the
     'X-CSRFToken' request header.
  3. Obtain the CSRF cookie automatically from the first login/signup
     response (both are decorated with @ensure_csrf_cookie).
"""

import uuid

from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

from notification.utils import create_notification

from .forms import SignupForm, ProfileForm
from .models import User, FriendshipRequest
from .serializers import UserSerializer, FriendshipRequestSerializer

# ---------------------------------------------------------------------------
# CSRF-enforcing authentication class for cookie endpoints
#
# DRF's @api_view bypasses Django's raw @csrf_protect decorator because DRF
# wraps the request before CSRF middleware can inspect it.  The correct DRF
# mechanism is to include a class that implements enforce_csrf().
# SessionAuthentication already does this — we use it here purely for its
# CSRF enforcement, not to require an active session.
# ---------------------------------------------------------------------------
class CsrfEnforcedNoAuth(SessionAuthentication):
    """
    Runs DRF's CSRF enforcement (via SessionAuthentication.enforce_csrf)
    without requiring or validating an actual session cookie.
    Returns None for both user and token (unauthenticated), but raises
    AuthenticationFailed if the CSRF token is missing or invalid.
    """
    def authenticate(self, request):
        # enforce_csrf raises AuthenticationFailed (→ 403) when the
        # X-CSRFToken header is absent or does not match the cookie.
        self.enforce_csrf(request)
        return None   # no authenticated user; other auth classes may follow
_REFRESH_COOKIE_NAME = 'refresh_token'
_REFRESH_COOKIE_PATH = '/api/'


def _set_refresh_cookie(response, refresh_token_str):
    """Attach the HttpOnly refresh-token cookie to *response*."""
    max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=refresh_token_str,
        max_age=max_age,
        path=_REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def _clear_refresh_cookie(response):
    """Expire the refresh-token cookie."""
    response.delete_cookie(
        key=_REFRESH_COOKIE_NAME,
        path=_REFRESH_COOKIE_PATH,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------
@ensure_csrf_cookie
@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def signup(request):
    """
    Register a new user.

    Request body: {email, name, password1, password2}

    Success response (200):
        {message: 'success', access: '<jwt>', user: {...}}
        Set-Cookie: refresh_token=<token>; HttpOnly; ...

    The refresh token is NOT included in the JSON body.
    """
    form = SignupForm({
        'email'    : request.data.get('email'),
        'name'     : request.data.get('name'),
        'password1': request.data.get('password1'),
        'password2': request.data.get('password2'),
    })

    if not form.is_valid():
        return JsonResponse({'message': form.errors.as_json()}, status=400)

    user = form.save()
    user.is_active = True
    user.save()

    refresh = RefreshToken.for_user(user)
    access_str  = str(refresh.access_token)
    refresh_str = str(refresh)

    response = JsonResponse({
        'message': 'success',
        'access' : access_str,
        'user'   : UserSerializer(user).data,
    })
    _set_refresh_cookie(response, refresh_str)
    return response


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@ensure_csrf_cookie
@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def login(request):
    """
    Authenticate with email + password.

    Request body: {email, password}

    Success response (200):
        {access: '<jwt>', user: {...}}
        Set-Cookie: refresh_token=<token>; HttpOnly; ...

    The refresh token is NOT included in the JSON body.
    """
    email    = request.data.get('email', '').strip()
    password = request.data.get('password', '')

    if not email or not password:
        return JsonResponse({'detail': 'Email and password are required.'}, status=400)

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return JsonResponse({'detail': 'No active account found with the given credentials.'}, status=401)

    if not user.check_password(password):
        return JsonResponse({'detail': 'No active account found with the given credentials.'}, status=401)

    if not user.is_active:
        return JsonResponse({'detail': 'No active account found with the given credentials.'}, status=401)

    refresh = RefreshToken.for_user(user)
    access_str  = str(refresh.access_token)
    refresh_str = str(refresh)

    response = JsonResponse({
        'access': access_str,
        'user'  : UserSerializer(user).data,
    })
    _set_refresh_cookie(response, refresh_str)
    return response


# ---------------------------------------------------------------------------
# Refresh — reads HttpOnly cookie, returns new access token
# ---------------------------------------------------------------------------
@api_view(['POST'])
@authentication_classes([CsrfEnforcedNoAuth])
@permission_classes([])
def refresh(request):
    """
    Issue a new access token using the HttpOnly refresh cookie.

    No request body required.

    Success response (200):
        {access: '<jwt>'}

    The refresh token is NOT returned and is not rotated
    (ROTATE_REFRESH_TOKENS = False).
    """
    refresh_str = request.COOKIES.get(_REFRESH_COOKIE_NAME)
    if not refresh_str:
        return JsonResponse({'detail': 'Refresh token not found.'}, status=401)

    try:
        token      = RefreshToken(refresh_str)
        access_str = str(token.access_token)
    except (InvalidToken, TokenError):
        response = JsonResponse({'detail': 'Invalid or expired refresh token.'}, status=401)
        _clear_refresh_cookie(response)
        return response

    return JsonResponse({'access': access_str})


# ---------------------------------------------------------------------------
# Logout — clears the refresh cookie
# ---------------------------------------------------------------------------
@api_view(['POST'])
@authentication_classes([CsrfEnforcedNoAuth])
@permission_classes([])
def logout(request):
    """
    Log the user out by expiring the refresh-token cookie.

    The frontend is responsible for clearing the access token from Pinia and
    removing the Axios Authorization header.

    Returns 200 whether or not the cookie was present (idempotent).
    """
    response = JsonResponse({'message': 'Logged out.'})
    _clear_refresh_cookie(response)
    return response


# ---------------------------------------------------------------------------
# WebSocket ticket — short-lived, single-use cache entry
# ---------------------------------------------------------------------------
@api_view(['GET'])
def ws_ticket(request):
    """
    Issue a 30-second, single-use ticket for WebSocket authentication.

    Requires a valid access token in the Authorization: Bearer header.
    The ticket is a UUID stored in Django's default cache with a 30 s TTL.
    The ChatConsumer reads it via ?ticket=<uuid>, validates it against the
    cache, and deletes it immediately (replay-proof).

    Success response (200):
        {ticket: '<uuid>'}
    """
    ticket = str(uuid.uuid4())
    user_id = str(request.user.pk)
    cache.set(
        f'ws_ticket:{ticket}',
        user_id,
        timeout=settings.WS_TICKET_TTL,
    )
    return JsonResponse({'ticket': ticket})


# ---------------------------------------------------------------------------
# User profile endpoints (unchanged)
# ---------------------------------------------------------------------------
@api_view(['GET'])
def me(request):
    return JsonResponse({
        'id'    : request.user.id,
        'name'  : request.user.name,
        'email' : request.user.email,
        'avatar': request.user.get_avatar(),
    })


@api_view(['GET'])
def friends(request, pk):
    user = User.objects.get(pk=pk)
    requests = []

    if user == request.user:
        requests = FriendshipRequest.objects.filter(
            created_for=request.user, status=FriendshipRequest.SENT
        )
        requests = FriendshipRequestSerializer(requests, many=True).data

    friends_qs = user.friends.all()
    return JsonResponse({
        'user'    : UserSerializer(user).data,
        'friends' : UserSerializer(friends_qs, many=True).data,
        'requests': requests,
    }, safe=False)


@api_view(['GET'])
def my_friendship_suggestions(request):
    serializer = UserSerializer(request.user.people_you_may_know.all(), many=True)
    return JsonResponse(serializer.data, safe=False)


@api_view(['POST'])
def editprofile(request):
    user  = request.user
    email = request.data.get('email')

    if User.objects.exclude(id=user.id).filter(email=email).exists():
        return JsonResponse({'message': 'email already exists'})

    form = ProfileForm(request.POST, request.FILES, instance=user)
    if form.is_valid():
        form.save()

    return JsonResponse({'message': 'information updated', 'user': UserSerializer(user).data})


@api_view(['POST'])
def editpassword(request):
    user = request.user
    form = PasswordChangeForm(data=request.POST, user=user)

    if form.is_valid():
        form.save()
        return JsonResponse({'message': 'success'})

    return JsonResponse({'message': form.errors.as_json()}, safe=False)


@api_view(['POST'])
def send_friendship_request(request, pk):
    user   = User.objects.get(pk=pk)
    check1 = FriendshipRequest.objects.filter(created_for=request.user).filter(created_by=user)
    check2 = FriendshipRequest.objects.filter(created_for=user).filter(created_by=request.user)

    if not check1 or not check2:
        friendrequest = FriendshipRequest.objects.create(
            created_for=user, created_by=request.user
        )
        create_notification(request, 'new_friendrequest', friendrequest_id=friendrequest.id)
        return JsonResponse({'message': 'friendship request created'})

    return JsonResponse({'message': 'request already sent'})


@api_view(['POST'])
def handle_request(request, pk, status):
    user               = User.objects.get(pk=pk)
    friendship_request = FriendshipRequest.objects.filter(
        created_for=request.user
    ).get(created_by=user)
    friendship_request.status = status
    friendship_request.save()

    user.friends.add(request.user)
    user.friends_count = user.friends_count + 1
    user.save()

    request_user = request.user
    request_user.friends_count = request_user.friends_count + 1
    request_user.save()

    create_notification(request, 'accepted_friendrequest', friendrequest_id=friendship_request.id)
    return JsonResponse({'message': 'friendship request updated'})
