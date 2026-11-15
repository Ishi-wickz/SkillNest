import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django_asgi_app = get_asgi_application()  # must run before importing anything that touches models

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.chat.routing import websocket_urlpatterns as chat_ws  # noqa: E402
from apps.notifications.routing import websocket_urlpatterns as notification_ws  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # The origin check stops other websites from opening sockets as your user
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(URLRouter(chat_ws + notification_ws))
    ),
})