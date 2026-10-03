"""
WebSocket consumer for the existing Frenzo chat system.

Authentication
--------------
Uses the project's existing JWT (djangorestframework-simplejwt).
The access token is passed in the WebSocket query string as ?token=<access>.
The token value is never written to logs.

Authorization
-------------
A user can only join a conversation they are a member of.  Guessing a
conversation UUID does not grant access.

Persistence
-----------
Messages are saved using the existing Conversation / ConversationMessage
models, identical to how the REST endpoint (conversation_send_message) does
it.  No migrations are required.

Channel layer
-------------
Uses InMemoryChannelLayer (channels.layers) — correct for channels 4.x on a
single-process Daphne server.  All clients connected to the same conversation
share one channel group named  "chat_<conversation_id>".
"""

from urllib.parse import parse_qs

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import Conversation, ConversationMessage
from .serializers import ConversationMessageSerializer

User = get_user_model()

# WebSocket close codes in the 4xxx application-defined range.
_CLOSE_UNAUTHORIZED = 4001   # bad / missing token
_CLOSE_FORBIDDEN    = 4003   # valid user, not a conversation member


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Real-time bidirectional chat for an existing Conversation."""

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]

        # 1. Authenticate via the existing JWT access token.
        user = await self._get_user_from_token()
        if user is None:
            await self.close(code=_CLOSE_UNAUTHORIZED)
            return

        # 2. Authorise: the user must already belong to this conversation.
        if not await self._is_member(conversation_id, user):
            await self.close(code=_CLOSE_FORBIDDEN)
            return

        self.conversation_id = conversation_id
        self.user            = user
        self.group_name      = f"chat_{conversation_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        group_name = getattr(self, "group_name", None)
        if group_name is not None:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    # ------------------------------------------------------------------
    # Incoming messages from the browser
    # ------------------------------------------------------------------

    async def receive_json(self, content, **kwargs):
        body = (content.get("body") or "").strip()
        if not body:
            return

        # Save using the existing models (same logic as the REST view).
        message     = await self._save_message(body)
        message_data = await self._serialize(message)

        # Broadcast to all group members (including the sender; the frontend
        # de-duplicates by message id so the sender will not see it twice).
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.message", "message": message_data},
        )

    # ------------------------------------------------------------------
    # Group event handlers (called by the channel layer)
    # ------------------------------------------------------------------

    async def chat_message(self, event):
        """Forward a group-broadcast message to this WebSocket client."""
        await self.send_json(event["message"])

    # ------------------------------------------------------------------
    # Database helpers (executed in a thread pool via database_sync_to_async)
    # ------------------------------------------------------------------

    @database_sync_to_async
    def _get_user_from_token(self):
        """
        Parse and validate the JWT access token from the WS query string.
        Returns the matching User, or None if invalid.
        The token value is not logged anywhere.
        """
        qs     = self.scope.get("query_string", b"").decode()
        params = parse_qs(qs)
        values = params.get("token")
        if not values:
            return None
        token_str = values[0]
        try:
            token   = AccessToken(token_str)
            user_id = token["user_id"]
            return User.objects.get(id=user_id)
        except (InvalidToken, TokenError, User.DoesNotExist, KeyError, ValueError):
            return None

    @database_sync_to_async
    def _is_member(self, conversation_id, user):
        """Return True only when the user is listed in the conversation."""
        return Conversation.objects.filter(
            id=conversation_id, users=user
        ).exists()

    @database_sync_to_async
    def _save_message(self, body):
        """
        Create a ConversationMessage, mirroring the REST send endpoint.
        The existing model's save() hook also updates Conversation.modified_at.
        """
        conversation = Conversation.objects.get(id=self.conversation_id)

        # Pick the other participant as sent_to (conversations are 1-to-1).
        sent_to = None
        for member in conversation.users.all():
            if member.pk != self.user.pk:
                sent_to = member
                break

        return ConversationMessage.objects.create(
            conversation=conversation,
            body=body,
            created_by=self.user,
            sent_to=sent_to,
        )

    @database_sync_to_async
    def _serialize(self, message):
        return ConversationMessageSerializer(message).data
