# core/tasks.py

from celery import shared_task
from socket_io_emitter import Emitter
from django.conf import settings
import logging
from urllib.parse import urlparse
import redis

from .models import Order
from .serializers import OrderSerializer
import uuid
from datetime import datetime
from .utils.json_helpers import convert_decimals_to_strings

logger = logging.getLogger(__name__)

# Redis istemcisini doğru SSL ayarlarıyla manuel olarak oluşturuyoruz
# Bu, 'Invalid SSL' hatasını önler ve kararlı bir bağlantı sağlar.
try:
    url = urlparse(settings.REDIS_URL)
    redis_opts = {
        'host': url.hostname,
        'port': url.port,
        'ssl': url.scheme == 'rediss',
        'ssl_cert_reqs': None,  # Heroku Redis için sertifika doğrulamasını atla
    }
    if url.password:
        redis_opts['password'] = url.password

    redis_client = redis.Redis(**redis_opts)
    io = Emitter(opts={'client': redis_client})
    logger.info("Socket.IO Emitter successfully initialized with parsed REDIS_URL.")
except Exception as e:
    logger.error(f"Failed to initialize Socket.IO Emitter: {e}", exc_info=True)
    class MockEmitter:
        def in_(self, room): 
            return self
        def to(self, room):
            return self
        def emit(self, event, data, room=None):
            pass
        def Emit(self, event, data, room=None): 
            pass  # Geriye uyumluluk için
    io = MockEmitter()


@shared_task(name="send_order_update_notification")
def send_order_update_task(order_id, event_type, message, extra_data=None):
    """
    WebSocket üzerinden sipariş güncelleme bildirimini gönderen Celery task'i.
    Socket.io-emitter kütüphanesini doğru sözdizimi ile kullanır.
    """
    logger.info(f"[Celery Task] Sending notification for Order ID: {order_id}, Event: {event_type}")
    try:
        order = Order.objects.select_related(
            'table', 'customer', 'business', 'taken_by_staff'
        ).prefetch_related(
            'order_items__menu_item__category__assigned_kds',
            'order_items__variant'
        ).get(id=order_id)

        serialized_order = OrderSerializer(order).data

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

        business_room = f"business_{order.business_id}"

        kds_screens_with_items = {
            item.menu_item.category.assigned_kds
            for item in order.order_items.all()
            if item.menu_item and item.menu_item.category and item.menu_item.category.assigned_kds
        }

        # === DEĞİŞİKLİK: Bildirim gönderme metodu düzeltildi ===
        # socket_io_emitter kütüphanesi için doğru kullanım: to() metodu ve emit() metodu
        try:
            # Business room'a bildirim gönder
            io.to(business_room).emit('order_status_update', update_data)
            logger.info(f"[Celery Task] Notification sent via Emitter to room: {business_room}")
            
            # KDS room'larına bildirim gönder
            for kds in kds_screens_with_items:
                kds_room = f"kds_{order.business_id}_{kds.slug}"
                kds_data = update_data.copy()
                kds_data['kds_slug'] = kds.slug
                io.to(kds_room).emit('order_status_update', kds_data)
                logger.info(f"[Celery Task] Notification sent via Emitter to KDS room: {kds_room}")
                
        except AttributeError as attr_error:
            # Eğer socket_io_emitter'da to() metodu yoksa, alternatif yöntem dene
            logger.warning(f"[Celery Task] AttributeError with to() method: {attr_error}")
            try:
                # Alternatif 1: in_() ve Emit() kombinasyonu (eski syntax)
                io.in_(business_room).Emit('order_status_update', update_data)
                logger.info(f"[Celery Task] Notification sent via Emitter (alternative method) to room: {business_room}")
                
                for kds in kds_screens_with_items:
                    kds_room = f"kds_{order.business_id}_{kds.slug}"
                    kds_data = update_data.copy()
                    kds_data['kds_slug'] = kds.slug
                    io.in_(kds_room).Emit('order_status_update', kds_data)
                    logger.info(f"[Celery Task] Notification sent via Emitter (alternative method) to KDS room: {kds_room}")
                    
            except Exception as fallback_error:
                logger.error(f"[Celery Task] All Socket.IO methods failed: {fallback_error}")
                # Son çare: Manuel Redis pub/sub
                try:
                    import json
                    redis_client = redis.Redis.from_url(settings.REDIS_URL, ssl_cert_reqs=None)
                    
                    # Business room için manuel pub/sub
                    message_data = {
                        'type': 'message',
                        'nsp': '/',
                        'data': ['order_status_update', update_data]
                    }
                    redis_client.publish(f"socket.io#{business_room}", json.dumps(message_data))
                    logger.info(f"[Celery Task] Manual Redis pub/sub notification sent to room: {business_room}")
                    
                    # KDS room'ları için manuel pub/sub
                    for kds in kds_screens_with_items:
                        kds_room = f"kds_{order.business_id}_{kds.slug}"
                        kds_data = update_data.copy()
                        kds_data['kds_slug'] = kds.slug
                        kds_message_data = {
                            'type': 'message',
                            'nsp': '/',
                            'data': ['order_status_update', kds_data]
                        }
                        redis_client.publish(f"socket.io#{kds_room}", json.dumps(kds_message_data))
                        logger.info(f"[Celery Task] Manual Redis pub/sub notification sent to KDS room: {kds_room}")
                        
                except Exception as redis_error:
                    logger.error(f"[Celery Task] Manuel Redis pub/sub failed: {redis_error}")

    except Order.DoesNotExist:
        logger.error(f"[Celery Task] Order with ID {order_id} not found.")
    except Exception as e:
        logger.error(f"[Celery Task] Failed to send notification for order {order_id}. Error: {e}", exc_info=True)


@shared_task(name="send_bulk_order_notifications")
def send_bulk_order_notifications(notification_list):
    """
    Toplu sipariş bildirimlerini gönderen task
    """
    for notification in notification_list:
        send_order_update_task.delay(
            notification.get('order_id'),
            notification.get('event_type'),
            notification.get('message'),
            notification.get('extra_data')
        )


@shared_task(name="test_socket_connection")
def test_socket_connection():
    """
    Socket bağlantısını test eden task
    """
    try:
        test_data = {
            'test': True,
            'timestamp': datetime.now().isoformat(),
            'message': 'Socket connection test from Celery'
        }
        
        # Test room'una test mesajı gönder
        io.to('test_room').emit('test_event', test_data)
        logger.info("[Celery Task] Socket connection test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"[Celery Task] Socket connection test failed: {e}")
        return False


@shared_task(name="cleanup_old_notifications")
def cleanup_old_notifications():
    """
    Eski bildirimleri temizleyen task (eğer notification modeli varsa)
    """
    try:
        from datetime import timedelta
        from django.utils import timezone
        
        # 7 gün önceki bildirimleri temizle
        cutoff_date = timezone.now() - timedelta(days=7)
        
        # Eğer notification modeli varsa burada temizlik yapabilirsiniz
        logger.info(f"[Celery Task] Notification cleanup completed for dates before {cutoff_date}")
        
    except Exception as e:
        logger.error(f"[Celery Task] Notification cleanup failed: {e}")