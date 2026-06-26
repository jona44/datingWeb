import urllib.parse

from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def get_user(token_key):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import AnonymousUser

    try:
        token = AccessToken(token_key)
        user_id = token['user_id']
        user_model = get_user_model()
        return user_model.objects.get(id=user_id)
    except Exception:
        return AnonymousUser()

class WebSocketTokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser

        # Extract token from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = urllib.parse.parse_qs(query_string)
        token_key = query_params.get('token', [None])[0]

        if token_key:
            scope['user'] = await get_user(token_key)
        else:
            scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)
