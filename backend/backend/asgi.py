"""
ASGI config for the backend project.

Routes HTTP requests to the standard Django application and WebSocket
requests to Django Channels. JWT authentication for WebSockets is handled
inside the ChatConsumer (token passed in the query string), so no
session-based AuthMiddlewareStack is needed here.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

# Must be called before importing anything that touches Django models.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
import chat.routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(chat.routing.websocket_urlpatterns),
    }
)
