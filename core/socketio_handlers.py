# core/socketio_handlers.py

from urllib.parse import parse_qs
from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from django.db import transaction
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
import logging
import asyncio
import time

# === HATA DÜZELTMESİ BURADA: İki nokta (..) tek noktaya (.) çevrildi ===
from .models import Order, Table, KDSScreen, Business, CustomUser
from .utils.order_helpers import get_user_business, PermissionKeys

logger = logging.getLogger(__name__)
User = get_user_model()

@database_sync_to_async
def get_user_from_token(token_key):
    """Verilen JWT token'ından kullanıcıyı doğrular ve döndürür."""
    User = get_user_model()
    try:
        access_token = AccessToken(token_key)
        user_id = access_token['user_id']
        user = User.objects.select_related(
            'owned_business', 'associated_business'
        ).prefetch_related('accessible_kds_screens').get(id=user_id)
        return user
    except (InvalidToken, TokenError, User.DoesNotExist) as e:
        logger.warning(f"SocketIO Token Hatası: {e} - Token (son 5): ...{token_key[-5:] if token_key and len(token_key) > 5 else token_key}")
        return None
    except Exception as e:
        logger.error(f"SocketIO Token'dan kullanıcı alınırken beklenmedik hata: {e}", exc_info=True)
        return None


@database_sync_to_async
def get_order_status_for_guest(table_uuid):
    try:
        table = Table.objects.get(uuid=table_uuid)
        active_guest_order = Order.objects.filter(
            table=table, customer__isnull=True, is_paid=False
        ).exclude(
            status__in=[Order.STATUS_REJECTED, Order.STATUS_CANCELLED, Order.STATUS_COMPLETED]
        ).order_by('-created_at').first()

        if active_guest_order:
            return {
                'event_type': 'initial_order_status_for_guest',
                'order_id': active_guest_order.id,
                'status': active_guest_order.status,
                'status_display': active_guest_order.get_status_display(),
                'message': f"Masa {table.table_number} için mevcut siparişinizin durumu: {active_guest_order.get_status_display()}"
            }
    except Table.DoesNotExist:
        logger.warning(f"Socket.IO (Misafir): Odaya katılımda {table_uuid} için masa bulunamadı.")
    except Exception as e:
        logger.error(f"Socket.IO (Misafir): {table_uuid} için başlangıç durumu alınırken hata: {e}", exc_info=True)
    return None

@database_sync_to_async
def can_user_access_kds(user, kds_slug, business):
    """Kullanıcının belirtilen KDS ekranına erişimi olup olmadığını kontrol eder."""
    try:
        kds_screen = KDSScreen.objects.get(slug=kds_slug, business=business, is_active=True)
        
        if user.user_type == 'business_owner' and user.owned_business == kds_screen.business:
            return True
        
        if user.user_type in ['staff', 'kitchen_staff']:
            if user.associated_business == kds_screen.business:
                return user.accessible_kds_screens.filter(id=kds_screen.id).exists()
        
        return False
    except KDSScreen.DoesNotExist:
        return False

def register_events(sio_server):
    @sio_server.event
    async def connect(sid, environ, auth):
        logger.info(f"Socket.IO bağlantı denemesi SID: {sid}")
        token = None
        if auth and isinstance(auth, dict) and 'token' in auth:
            token = auth.get('token')
        
        if not token:
            query_string = environ.get('QUERY_STRING', '')
            qs = parse_qs(query_string)
            token_list = qs.get('token')
            if token_list:
                token = token_list[0]

        if token:
            user = await get_user_from_token(token)
            if user and user.is_authenticated:
                user_business = await database_sync_to_async(get_user_business)(user)
                if user_business:
                    business_id = user_business.id
                    
                    user_room_name = f'user_{user.id}'
                    await sio_server.enter_room(sid, user_room_name)
                    logger.info(f"Socket.IO (Connect): İstemci {sid} (Kullanıcı ID: {user.id}) kişisel odasına '{user_room_name}' katıldı.")
                    
                    business_room_name = f'business_{business_id}'
                    await sio_server.enter_room(sid, business_room_name)
                    logger.info(f"Socket.IO (Connect): İstemci {sid} (Kullanıcı ID: {user.id}) genel işletme odasına '{business_room_name}' katıldı.")

                    await sio_server.save_session(sid, {
                        'user_id': user.id,
                        'user_type': user.user_type,
                        'business_id': business_id,
                        'type': 'authenticated_user'
                    })
                    
                    await sio_server.emit('connected_and_ready', {'sid': sid}, room=sid)
                    logger.info(f"Socket.IO: İstemci {sid} (Kullanıcı ID: {user.id}) bağlandı. 'connected_and_ready' olayı gönderildi.")
                    return True
                else:
                    logger.warning(f"Socket.IO: İstemci {sid} (Kullanıcı: {user.username}) için işletme bilgisi bulunamadı. Bağlantı reddedildi.")
                    return False
            else:
                logger.warning(f"Socket.IO: İstemci {sid} bağlantısı reddedildi (Geçersiz/yetkisiz token).")
                return False
        else:
            logger.info(f"Socket.IO: İstemci {sid} tokensiz bağlandı.")
            await sio_server.save_session(sid, {'type': 'guest_candidate'})
            return True

    @sio_server.event
    async def disconnect(sid):
        session = await sio_server.get_session(sid)
        if session:
            logger.info(f"Socket.IO: İstemci {sid} (Kullanıcı ID: {session.get('user_id', 'Bilinmiyor')}) bağlantısı kesildi.")
        else:
            logger.info(f"Socket.IO: İstemci {sid} bağlantısı kesildi (session bilgisi yok).")

    # 🔥 HEARTBEAT EVENTİ - HEROKU BAĞLANTI KONTROLÜ
    @sio_server.event
    async def heartbeat(sid, data):
        """
        Flutter istemcisinden gelen heartbeat paketlerini işler ve response gönderir.
        Bu, Heroku'nun bağlantı kesme davranışını engellemek için kullanılır.
        """
        session = await sio_server.get_session(sid)
        
        # Heartbeat response'u hemen geri gönder
        await sio_server.emit('heartbeat_response', {
            'timestamp': int(time.time() * 1000),
            'sid': sid
        }, room=sid)
        
        # Debug için log - sadece authenticated user'lar için detaylı log
        if session and session.get('type') == 'authenticated_user':
            user_id = session.get('user_id', 'Unknown')
            logger.debug(f"💓 Heartbeat alındı ve response gönderildi - SID: {sid}, User: {user_id}")
        else:
            logger.debug(f"💓 Heartbeat alındı (guest) - SID: {sid}")

    @sio_server.event
    async def join_kds_room(sid, data):
        session = await sio_server.get_session(sid)
        if not session or session.get('type') != 'authenticated_user':
            logger.warning(f"Socket.IO (KDS Join): SID {sid} için geçerli bir session bulunamadı.")
            return

        kds_slug = data.get('kds_slug')
        user_id = session.get('user_id')
        business_id = session.get('business_id')

        if not all([kds_slug, user_id, business_id]):
            logger.warning(f"Socket.IO (KDS Join): SID {sid} için session'dan veri alınamadı.")
            return

        try:
            user = await database_sync_to_async(User.objects.get)(id=user_id)
            business = await database_sync_to_async(Business.objects.get)(id=business_id)
        except (User.DoesNotExist, Business.DoesNotExist):
            logger.error(f"Socket.IO (KDS Join): SID {sid} için Kullanıcı veya İşletme bulunamadı.")
            return

        has_access = await can_user_access_kds(user, kds_slug, business)
        
        if has_access:
            if 'current_kds_room' in session and session['current_kds_room']:
                await sio_server.leave_room(sid, session['current_kds_room'])
                logger.info(f"Socket.IO (KDS): İstemci {sid} eski KDS odasından '{session['current_kds_room']}' ayrıldı.")

            kds_room_name = f'kds_{business_id}_{kds_slug}'
            await sio_server.enter_room(sid, kds_room_name)
            
            session['current_kds_room'] = kds_room_name
            await sio_server.save_session(sid, session)
            
            logger.info(f"Socket.IO (KDS): İstemci {sid} (Kullanıcı: {user.username}) EK OLARAK '{kds_room_name}' odasına başarıyla katıldı.")
        else:
            logger.warning(f"Socket.IO (KDS Join): SID {sid} kullanıcısı {user.username}, KDS ekranı '{kds_slug}' için YETKİSİZ.")

    @sio_server.event
    async def join_guest_table_room(sid, data):
        table_uuid = data.get('table_uuid')
        session = await sio_server.get_session(sid)

        if table_uuid and session and session.get('type') == 'guest_candidate':
            if 'room_name' in session and session['room_name']:
                await sio_server.leave_room(sid, session['room_name'])

            guest_room_name = f'guest_table_{table_uuid}'
            await sio_server.enter_room(sid, guest_room_name)
            
            session['room_name'] = guest_room_name
            session['current_room_name'] = guest_room_name
            session['type'] = 'guest_user'
            session['table_uuid'] = table_uuid
            await sio_server.save_session(sid, session)
            logger.info(f"Socket.IO (Misafir): İstemci {sid}, '{guest_room_name}' odasına katıldı.")

            initial_status_payload = await get_order_status_for_guest(table_uuid)
            if initial_status_payload:
                await sio_server.emit('order_update_for_guest_table', initial_status_payload, room=sid)
                logger.info(f"Socket.IO (Misafir): Başlangıç sipariş durumu {sid} istemcisine gönderildi: {initial_status_payload}")
            return True
        elif session and session.get('type') != 'guest_candidate':
            logger.warning(f"Socket.IO (Misafir): İstemci {sid} zaten farklı bir tipte ({session.get('type')}) bağlanmış, misafir odasına katılamaz.")
            return False
        else:
            logger.warning(f"Socket.IO (Misafir): İstemci {sid} 'join_guest_table_room' için table_uuid sağlamadı veya geçerli bir session'a sahip değil.")
            return False