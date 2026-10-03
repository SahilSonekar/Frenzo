from django.urls import re_path

from . import consumers

# WebSocket URL patterns for the existing chat system.
#
# A client connects to:
#   ws://host/ws/chat/<conversation_id>/?token=<jwt_access_token>
#
# conversation_id is the UUID primary key of an existing Conversation
# (hex digits and hyphens, e.g. "8281e93a-6252-4800-8671-397898c4a1c5").
websocket_urlpatterns = [
    re_path(
        r"^ws/chat/(?P<conversation_id>[0-9a-f-]+)/$",
        consumers.ChatConsumer.as_asgi(),
    ),
]
