# core/middleware.py

from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import UntypedToken
from django.contrib.auth import get_user_model
from django.conf import settings
from jwt import decode as jwt_decode, InvalidTokenError

@database_sync_to_async
def get_user_from_token(token):
    try:
        # Token geçerliliğini kontrol ediyoruz
        UntypedToken(token)
    except Exception:
        return AnonymousUser()
    User = get_user_model()
    try:
        # Token'ı çözerek kullanıcıyı getiriyoruz
        decoded_data = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user = User.objects.get(id=decoded_data["user_id"])
        return user
    except User.DoesNotExist:
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # URL query string içerisinden "token" sorgusunu alıyoruz
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token_list = query_params.get('token')
        if token_list:
            token = token_list[0]
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()
        return await super().__call__(scope, receive, send)
