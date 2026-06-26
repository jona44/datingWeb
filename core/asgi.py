import os

import django
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import messaging.routing

from .middleware import WebSocketTokenAuthMiddleware

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": WebSocketTokenAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(messaging.routing.websocket_urlpatterns)
        )
    ),
})
