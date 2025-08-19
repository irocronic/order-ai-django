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
    logger.info("Redis client successfully initialized.")
    
except Exception as e:
    logger.error(f"Failed to initialize Redis client: {e}")
    redis_client = None


def send_socket_io_notification(room, event, data):
    """
    Socket.IO bildirimi gönderen yardımcı fonksiyon - DÜZELTİLMİŞ VERSİYON
    """
    success = False
    
    # Method 1: ASGI app üzerinden direkt emit (en güvenilir)
    try:
        from makarna_project.asgi import sio
        import asyncio
        
        # Async fonksiyonu sync context'te çalıştır
        async def emit_notification():
            await sio.emit(event, data, room=room)
            
        # Event loop kontrolü
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Async context içindeyiz, task olarak schedule et
                asyncio.create_task(emit_notification())
            else:
                # Sync context, event loop çalıştır
                loop.run_until_complete(emit_notification())
        except RuntimeError:
            # Event loop yok, yeni bir tane oluştur
            asyncio.run(emit_notification())
            
        logger.info(f"[Notification] Sent via Socket.IO server to room: {room}")
        success = True
        
    except Exception as e:
        logger.error(f"[Notification] Direct Socket.IO emit failed: {e}")
    
    # Method 2: Redis pub/sub - DOĞRU FORMAT
    if not success and redis_client:
        try:
            # Socket.IO'nun beklediği Redis message formatı
            message = {
                "uid": "emitter",
                "type": 2,  # EVENT type
                "data": [event, data],
                "nsp": "/"
            }
            
            # Socket.IO room key formatı
            room_key = f"socket.io#{room}"
            
            # JSON encode et ve gönder
            redis_client.publish(room_key, json.dumps(message))
            logger.info(f"[Notification] Sent via Redis pub/sub to room: {room}")
            success = True
            
        except Exception as e:
            logger.error(f"[Notification] Redis pub/sub failed: {e}")
    
    # Method 3: HTTP webhook fallback
    if not success:
        try:
            import requests
            
            # Webhook endpoint (eğer varsa)
            webhook_url = "https://order-ai-7bd2c97ec9ef.herokuapp.com/api/webhook/socket-emit/"
            payload = {
                'room': room,
                'event': event,
                'data': data
            }
            
            response = requests.post(webhook_url, json=payload, timeout=5)
            if response.status_code == 200:
                logger.info(f"[Notification] Sent via HTTP webhook to room: {room}")
                success = True
            else:
                logger.debug(f"[Notification] HTTP webhook not available: {response.status_code}")
                
        except Exception as e:
            logger.debug(f"[Notification] HTTP webhook not available: {e}")
    
    return success


@shared_task(name="send_order_update_notification")
def send_order_update_task(order_id, event_type, message, extra_data=None):
    """
    WebSocket üzerinden sipariş güncelleme bildirimini gönderen Celery task'i.
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

        # 🔥 YENİ: Test için manuel emit de ekle
        test_notification_data = {
            'event_type': f'{event_type}_manual',
            'order_id': order.id,
            'message': f'Manual test: {message}',
            'notification_id': f"manual_{uuid.uuid4()}",
            'timestamp': datetime.now().isoformat()
        }
        
        # Test bildirimini de gönder
        send_socket_io_notification(business_room, 'order_status_update', test_notification_data)
        logger.info(f"[Celery Task] 🧪 Test notification sent for order {order_id}")

        # Sonuç raporu
        if business_success:
            logger.info(f"[Celery Task] ✅ Business notification sent successfully for order {order_id}")
        else:
            logger.error(f"[Celery Task] ❌ Business notification failed for order {order_id}")
            
        if kds_success_count == len(kds_screens_with_items):
            logger.info(f"[Celery Task] ✅ All KDS notifications sent successfully for order {order_id}")
        else:
            logger.warning(f"[Celery Task] ⚠️ KDS notifications: {kds_success_count}/{len(kds_screens_with_items)} successful for order {order_id}")

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
            'event_type': 'test_notification',
            'test': True,
            'timestamp': datetime.now().isoformat(),
            'message': 'Socket connection test from Celery',
            'notification_id': f"test_{uuid.uuid4()}"
        }
        
        # Test room'una test mesajı gönder
        success = send_socket_io_notification('business_67', 'order_status_update', test_data)
        
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
        
        logger.info(f"[Celery Task] Notification cleanup completed for dates before {cutoff_date}")
        
    except Exception as e:
        logger.error(f"[Celery Task] Notification cleanup failed: {e}")


# 🔥 YENİ: Manuel test task'ı
@shared_task(name="send_test_notification")
def send_test_notification(business_id=67):
    """
    Manual test bildirimi gönderen task
    """
    test_data = {
        'event_type': 'order_approved_for_kitchen',
        'order_id': 99999,
        'table_number': 999,
        'message': '🧪 Backend test bildirimi - Manuel gönderim',
        'notification_id': f"manual_test_{uuid.uuid4()}",
        'timestamp': datetime.now().isoformat()
    }
    
    room = f"business_{business_id}"
    success = send_socket_io_notification(room, 'order_status_update', test_data)
    
    if success:
        logger.info(f"[Celery Task] 🧪 Manual test notification sent to {room}")
        return True
    else:
        logger.error(f"[Celery Task] 🧪 Manual test notification failed for {room}")
        return False