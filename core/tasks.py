from celery import shared_task
from socketio.redis_emitter import RedisEmitter  # Doğru import
from django.conf import settings
import logging
from .models import Order
from .serializers import OrderSerializer
import uuid
from datetime import datetime
from .utils.json_helpers import convert_decimals_to_strings

# Logger'ı başlat
logger = logging.getLogger(__name__)

# Celery worker'ının mesajları yayınlayacağı Redis istemcisini oluştur
# Bu, ana web sunucusunun (ASGI) dinlediği Redis kanalına mesaj gönderir.
sio_redis_emitter = RedisEmitter(settings.REDIS_URL, write_only=True)

@shared_task(name="send_order_update_notification")
def send_order_update_task(order_id, event_type, message, extra_data=None):
    """
    WebSocket üzerinden sipariş güncelleme bildirimini gönderen Celery task'i.
    Artık RedisEmitter kullanarak ana web process ile iletişim kurar.
    """
    logger.info(f"[Celery Task] Sending notification for Order ID: {order_id}, Event: {event_type}")
    try:
        # İlgili siparişi veritabanından al
        order = Order.objects.select_related(
            'table', 'customer', 'business', 'taken_by_staff'
        ).prefetch_related(
            'order_items__menu_item__category__assigned_kds',
            'order_items__variant'
        ).get(id=order_id)

        # Sipariş verisini serialize et
        serialized_order = OrderSerializer(order).data
        
        # Flutter'a gönderilecek olan bildirim payload'ını oluştur
        update_data = {
            'notification_id': f"{uuid.uuid4()}",
            'event_type': event_type,
            'message': message,
            'order_id': order.id,
            'updated_order_data': convert_decimals_to_strings(serialized_order),
            'table_number': order.table.table_number if order.table else None,
            'timestamp': datetime.now().isoformat()
        }
        if extra_data:
            update_data.update(extra_data)

        # Bildirimin gönderileceği odaları belirle
        business_room = f"business_{order.business_id}"
        
        # Siparişteki ürünlerin hangi KDS ekranlarına ait olduğunu bul
        kds_screens_with_items = {
            item.menu_item.category.assigned_kds
            for item in order.order_items.all()
            if item.menu_item and item.menu_item.category and item.menu_item.category.assigned_kds
        }

        # Bildirimi Redis üzerinden genel işletme odasına yayınla
        sio_redis_emitter.emit('order_status_update', update_data, room=business_room)
        logger.info(f"[Celery Task] Notification EMITTED VIA REDIS to room: {business_room}")

        # Bildirimi ilgili tüm KDS odalarına da yayınla
        for kds in kds_screens_with_items:
            kds_room = f"kds_{order.business_id}_{kds.slug}"
            kds_data = update_data.copy()
            kds_data['kds_slug'] = kds.slug
            sio_redis_emitter.emit('order_status_update', kds_data, room=kds_room)
            logger.info(f"[Celery Task] Notification EMITTED VIA REDIS to KDS room: {kds_room}")
    
    except Order.DoesNotExist:
        logger.error(f"[Celery Task] Order with ID {order_id} not found.")
    except Exception as e:
        logger.error(f"[Celery Task] Failed to send notification for order {order_id}. Error: {e}", exc_info=True)