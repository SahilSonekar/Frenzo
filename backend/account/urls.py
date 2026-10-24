from django.urls import path

from . import api

urlpatterns = [
    # ── Authentication ──────────────────────────────────────────────────────
    # signup   — register; returns {message, access, user} + refresh cookie
    path('signup/',  api.signup,  name='signup'),
    # login    — authenticate; returns {access, user} + refresh cookie
    path('login/',   api.login,   name='login'),
    # refresh  — reads refresh cookie; returns {access}  (no body needed)
    path('refresh/', api.refresh, name='token_refresh'),
    # logout   — expires the refresh cookie
    path('logout/',  api.logout,  name='logout'),
    # ws-ticket — short-lived single-use ticket for WebSocket auth
    path('ws-ticket/', api.ws_ticket, name='ws_ticket'),

    # ── User profile ────────────────────────────────────────────────────────
    path('me/',               api.me,                      name='me'),
    path('editprofile/',      api.editprofile,              name='editprofile'),
    path('editpassword/',     api.editpassword,             name='editpassword'),

    # ── Friends ─────────────────────────────────────────────────────────────
    path('friends/suggested/',               api.my_friendship_suggestions, name='my_friendship_suggestions'),
    path('friends/<uuid:pk>/',               api.friends,                   name='friends'),
    path('friends/<uuid:pk>/request/',       api.send_friendship_request,   name='send_friendship_request'),
    path('friends/<uuid:pk>/<str:status>/',  api.handle_request,            name='handle_request'),
]
