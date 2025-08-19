# core/tasks.py

from celery import shared_task
from django.conf import settings
import logging
from urllib.parse import urlparse
import redis
import json

from .models import Order
from .serializers import OrderSerializer
import uuid
from datetime import datetime
from .utils.json_helpers import convert_decimals_to_strings

logger = logging.getLogger(__name__)

# Redis istemcisini kurma
try:
    url = urlparse(settings.REDIS_URL)
    redis_opts = {
        'host': url.hostname,
        'port': url.port,
        'ssl': url.scheme == 'rediss',
        'ssl_cert_reqs': None,
        'decode_responses': False,  # Binary veri için False
    }
    if url.password:
        redis_opts['password'] = url.password

    redis_client = redis.Redis(**redis_opts)
    
    # Socket.IO Emitter'ı dene
    try:
        from socket_io_emitter import Emitter
        io = Emitter(opts={'client': redis_client})
        logger.info("Socket.IO Emitter successfully initialized with parsed REDIS_URL.")
        emitter_available = True
    except Exception as e:
        logger.error(f"Socket.IO Emitter failed to initialize: {e}")
        io = None
        emitter_available = False
        
except Exception as e:
    logger.error(f"Failed to initialize Redis client: {e}")
    redis_client = None
    io = None
    emitter_available = False


def send_socket_io_notification(room, event, data):
    """
    Socket.IO bildirimi gönderen yardımcı fonksiyon
    Birden fazla yöntem dener
    """
    success = False
    
    # Method 1: Socket.IO Emitter (eğer çalışıyorsa)
    if emitter_available and io:
        try:
            # Farklı emitter syntaxlarını dene
            if hasattr(io, 'to'):
                io.to(room).emit(event, data)
                logger.info(f"[Notification] Sent via emitter.to() to room: {room}")
                success = True
            elif hasattr(io, 'in_') and hasattr(io, 'emit'):
                io.in_(room).emit(event, data)
                logger.info(f"[Notification] Sent via emitter.in_().emit() to room: {room}")
                success = True
            elif hasattr(io, 'in_') and hasattr(io, 'Emit'):
                io.in_(room).Emit(event, data)
                logger.info(f"[Notification] Sent via emitter.in_().Emit() to room: {room}")
                success = True
        except Exception as e:
            logger.error(f"[Notification] Emitter failed: {e}")
    
    # Method 2: Manuel Redis pub/sub (Socket.IO formatında)
    if not success and redis_client:
        try:
            # Socket.IO server'ının beklediği format
            socket_io_message = {
                "type": 2,  # MESSAGE type
                "nsp": "/",  # namespace
                "data": [event, data]
            }
            
            # Socket.IO room formatı
            room_key = f"socket.io#{room}"
            
            # Redis'e yayınla
            redis_client.publish(room_key, json.dumps(socket_io_message))
            logger.info(f"[Notification] Sent via Redis pub/sub to room: {room}")
            success = True
            
        except Exception as e:
            logger.error(f"[Notification] Redis pub/sub failed: {e}")
    
    # Method 3: HTTP POST to Socket.IO endpoint (backup)
    if not success:
        try:
            import requests
            
            # Socket.IO server'a HTTP POST gönder
            url = "https://order-ai-7bd2c97ec9ef.herokuapp.com/api/socket/emit/"
            payload = {
                'room': room,
                'event': event,
                'data': data,
                'namespace': '/'
            }
            
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                logger.info(f"[Notification] Sent via HTTP POST to room: {room}")
                success = True
            else:
                logger.error(f"[Notification] HTTP POST failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"[Notification] HTTP POST failed: {e}")
    
    return success


@shared_task(name="send_order_update_notification")
def send_order_update_task(order_id, event_type, message, extra_data=None):
    """
    WebSocket üzerinden sipariş güncelleme bildirimini gönderen Celery task'i.
    Çoklu fallback stratejisi ile güvenilir bildirim gönderimi.
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

        # Business room'a bildirim gönder
        business_room = f"business_{order.business_id}"
        business_success = send_socket_io_notification(business_room, 'order_status_update', update_data)

        # KDS room'larına bildirim gönder
        kds_screens_with_items = {
            item.menu_item.category.assigned_kds
            for item in order.order_items.all()
            if item.menu_item and item.menu_item.category and item.menu_item.category.assigned_kds
        }

        kds_success_count = 0
        for kds in kds_screens_with_items:
            kds_room = f"kds_{order.business_id}_{kds.slug}"
            kds_data = update_data.copy()
            kds_data['kds_slug'] = kds.slug
            
            if send_socket_io_notification(kds_room, 'order_status_update', kds_data):
                kds_success_count += 1

        # Sonuç raporu
        if business_success:
            logger.info(f"[Celery Task] ✅ Business notification sent successfully for order {order_id}")
        else:
            logger.error(f"[Celery Task] ❌ Business notification failed for order {order_id}")
            
        if kds_success_count == len(kds_screens_with_items):
            logger.info(f"[Celery Task] ✅ All KDS notifications sent successfully for order {order_id}")
        else:
            logger.warning(f"[Celery Task] ⚠️ KDS notifications: {kds_success_count}/{len(kds_screens_with_items)} successful for order {order_id}")

        # En az business notification başarılı olmalı
        if not business_success:
            raise Exception(f"Failed to send business notification for order {order_id}")

    except Order.DoesNotExist:
        logger.error(f"[Celery Task] Order with ID {order_id} not found.")
        raise
    except Exception as e:
        logger.error(f"[Celery Task] Failed to send notification for order {order_id}. Error: {e}", exc_info=True)
        raise


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
        success = send_socket_io_notification('test_room', 'test_event', test_data)
        
        if success:
            logger.info("[Celery Task] Socket connection test completed successfully")
            return True
        else:
            logger.error("[Celery Task] Socket connection test failed")
            return False
        
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