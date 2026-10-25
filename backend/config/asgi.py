import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
from django.core.asgi import get_asgi_application
django_asgi=get_asgi_application()
from django.conf import settings
from django.urls import path
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter,URLRouter
from channels.security.websocket import OriginValidator
from platform_app.consumers import ChatConsumer
application=ProtocolTypeRouter({'http':django_asgi,'websocket':OriginValidator(AuthMiddlewareStack(URLRouter([path('ws/chat/',ChatConsumer.as_asgi())])),settings.CHAT_ALLOWED_ORIGINS)})
