"""
WebSocket consumer for the Frenzo chat system.

Authentication
--------------
A client must obtain a short-lived, single-use ticket before opening the
WebSocket connection:

    GET /api/ws-ticket/          (requires Authorization: Bearer <access>)
    ← {ticket: '<uuid>'}

Then connect to:

    ws://host/ws/chat/<conversation_id>/?ticket=<uuid>

The ticket is a UUID stored in Django's default cache with a 30-second TTL.
The consumer looks it up and deletes it on first use, making it replay-proof.
The full access JWT is never placed in a URL.

Authorization
-------------
A user can only join a conversation they are a member of. Knowing the
conversation UUID does not grant access.

Persistence
-----------
Messages are saved using the existing Conversation / ConversationMessage
models, identical to the REST endpoint. No migrations are required.

Channel layer
-------------
Uses InMemoryChannelLayer — correct for a single-process Daphne server.
"""

from urllib.parse import parse_qs

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.cache import cache

from .models import Conversation, ConversationMessage
from .serializers import ConversationMessageSerializer

User = get_user_model()

_CLOSE_UNAUTHORIZED = 4001   # bad / missing ticket
_CLOSE_FORBIDDEN    = 4003   # valid user, not a conversation member


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Real-time bidirectional chat for an existing Conversation."""

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        conversation_id = self.scope['url_route']['kwargs']['conversation_id']

        # 1. Authenticate via the single-use WS ticket.
        user = await self._get_user_from_ticket()
        if user is None:
            await self.close(code=_CLOSE_UNAUTHORIZED)
            return

        # 2. Authorise: the user must belong to this conversation.
        if not await self._is_member(conversation_id, user):
            await self.close(code=_CLOSE_FORBIDDEN)
            return

        self.conversation_id = conversation_id
        self.user            = user
        self.group_name      = f'chat_{conversation_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        group_name = getattr(self, 'group_name', None)
        if group_name is not None:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    # ------------------------------------------------------------------
    # Incoming messages from the browser
    # ------------------------------------------------------------------

    async def receive_json(self, content, **kwargs):
        body = (content.get('body') or '').strip()
        if not body:
            return

        message      = await self._save_message(body)
        message_data = await self._serialize(message)

        # Broadcast to the whole conversation group (including the sender;
        # the frontend de-duplicates by message id).
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'chat.message', 'message': message_data},
        )

    # ------------------------------------------------------------------
    # Group event handler
    # ------------------------------------------------------------------

    async def chat_message(self, event):
        await self.send_json(event['message'])

    # ------------------------------------------------------------------
    # Database / cache helpers
    # ------------------------------------------------------------------

    @database_sync_to_async
    def _get_user_from_ticket(self):
        """
        Validate the single-use WS ticket from the query string.
        Deletes the cache entry on first use (replay-proof).
        Returns the User, or None if the ticket is absent / invalid / expired.
        The ticket value is never logged.
        """
        qs      = self.scope.get('query_string', b'').decode()
        params  = parse_qs(qs)
        tickets = params.get('ticket')
        if not tickets:
            return None
        ticket  = tickets[0]
        cache_key = f'ws_ticket:{ticket}'

        user_id = cache.get(cache_key)
        if not user_id:
            return None

        # One-time use: delete immediately.
        cache.delete(cache_key)

        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def _is_member(self, conversation_id, user):
        return Conversation.objects.filter(id=conversation_id, users=user).exists()

    @database_sync_to_async
    def _save_message(self, body):
        conversation = Conversation.objects.get(id=self.conversation_id)
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
