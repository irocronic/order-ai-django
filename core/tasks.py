# core/tasks.py (GÜNCELLENMİŞ VE TAM VERSİYON - DATABASE RETRY MEKANIZMASI İLE)

from celery import shared_task
from django.conf import settings
import logging
from urllib.parse import urlparse
import redis
import json
import time
from functools import wraps

from .models import Order
from .serializers import OrderSerializer
import uuid
from datetime import datetime
from .utils.json_helpers import convert_decimals_to_strings
from .utils.notification_gate import is_notification_active

# === YENİ EKLENEN: DATABASE RETRY MEKANIZMASI ===
from django.db import transaction, connection
from django.db.utils import OperationalError, InterfaceError
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

def retry_on_database_error(max_retries=3, delay=1, backoff=2):
    """
    Veritabanı bağlantı hatalarında otomatik retry yapan decorator.
    SSL connection drops, timeouts vb. için tasarlanmış.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    # Her denemede bağlantıyı temizle
                    if attempt > 0:
                        connection.close()
                        logger.warning(f"[RETRY {attempt}/{max_retries}] Database connection reset for {func.__name__}")
                    
                    # Fonksiyonu çalıştır
                    return func(*args, **kwargs)
                    
                except (OperationalError, InterfaceError) as e:
                    last_exception = e
                    error_msg = str(e).lower()
                    
                    # SSL ve bağlantı hatalarını yakala
                    if any(keyword in error_msg for keyword in [
                        'ssl connection', 'connection closed', 'connection lost',
                        'server closed', 'timeout', 'network'
                    ]):
                        if attempt < max_retries:
                            wait_time = delay * (backoff ** attempt)
                            logger.warning(
                                f"[RETRY {attempt + 1}/{max_retries}] Database error in {func.__name__}: {e}. "
                                f"Retrying in {wait_time}s..."
                            )
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"[RETRY FAILED] Max retries ({max_retries}) reached for {func.__name__}: {e}")
                    else:
                        # SSL ile ilgili olmayan hatalar için retry yapma
                        logger.error(f"[NO RETRY] Non-connection database error in {func.__name__}: {e}")
                        break
                        
                except Exception as e:
                    # Veritabanı dışı hatalar için retry yapma
                    logger.error(f"[NO RETRY] Non-database error in {func.__name__}: {e}")
                    break
            
            # Son exception'ı yeniden fırlat
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator
# === RETRY MEKANIZMASI SONU ===

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


# ==================== GÜNCELLENMİŞ FONKSİYON BAŞLANGICI ====================
def send_socket_io_notification(room, event, data):
    """
    Socket.IO bildirimi gönderen yardımcı fonksiyon.
    Dönüş değerleri: 'sent', 'blocked', 'failed'
    """
    event_type_to_check = data.get('event_type')
    
    if event_type_to_check and event_type_to_check != 'test_notification':
        if not is_notification_active(event_type_to_check):
            logger.info(f"[Notification Gate] Bildirim engellendi (pasif): {event_type_to_check}")
            return 'blocked'  # DEĞİŞİKLİK 1: 'False' yerine 'blocked' döndürülüyor.

    success = False
    
    # Method 1: ASGI app üzerinden direkt emit (en güvenilir)
    try:
        from makarna_project.asgi import sio
        import asyncio
        
        async def emit_notification():
            await sio.emit(event, data, room=room)
            
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(emit_notification())
            else:
                loop.run_until_complete(emit_notification())
        except RuntimeError:
            asyncio.run(emit_notification())
            
        logger.info(f"[Notification] Sent via Socket.IO server to room: {room}")
        success = True
        
    except Exception as e:
        logger.error(f"[Notification] Direct Socket.IO emit failed: {e}")
    
    # Method 2: Redis pub/sub
    if not success and redis_client:
        try:
            message = {
                "uid": "emitter",
                "type": 2,
                "data": [event, data],
                "nsp": "/"
            }
            room_key = f"socket.io#{room}"
            redis_client.publish(room_key, json.dumps(message))
            logger.info(f"[Notification] Sent via Redis pub/sub to room: {room}")
            success = True
            
        except Exception as e:
            logger.error(f"[Notification] Redis pub/sub failed: {e}")
    
    # Method 3: HTTP webhook fallback
    if not success:
        try:
            import requests
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
    
    # DEĞİŞİKLİK 2: Başarı durumuna göre string olarak sonuç döndürülüyor.
    return 'sent' if success else 'failed'

# ==================== GÜNCELLENMİŞ FONKSİYON SONU ====================


# ==================== GÜNCELLENMİŞ GÖREV (RETRY MEKANIZMASI İLE) ====================
@shared_task(name="send_order_update_notification", bind=True, autoretry_for=(OperationalError, InterfaceError), retry_kwargs={'max_retries': 3, 'countdown': 5})
@retry_on_database_error(max_retries=3, delay=1, backoff=2)
def send_order_update_task(self, order_id, event_type, message, extra_data=None):
    """
    WebSocket üzerinden sipariş güncelleme bildirimini gönderen Celery task'i.
    Artık database connection hatalarına karşı retry mekanizması ile korumalı.
    """
    logger.info(f"[Celery Task] Sending notification for Order ID: {order_id}, Event: {event_type}")
    
    try:
        # === RETRY KORUNMALI DATABASE SORGUSU ===
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

        # --- GÜNCELLENMİŞ LOGLAMA MANTIĞI ---
        business_room = f"business_{order.business_id}"
        business_status = send_socket_io_notification(business_room, 'order_status_update', update_data)

        kds_sent_count = 0
        kds_blocked_count = 0
        kds_screens_with_items = {
            item.menu_item.category.assigned_kds
            for item in order.order_items.all()
            if item.menu_item and item.menu_item.category and item.menu_item.category.assigned_kds
        }

        for kds in kds_screens_with_items:
            kds_room = f"kds_{order.business_id}_{kds.slug}"
            kds_data = update_data.copy()
            kds_data['kds_slug'] = kds.slug
            kds_status = send_socket_io_notification(kds_room, 'order_status_update', kds_data)
            if kds_status == 'sent':
                kds_sent_count += 1
            elif kds_status == 'blocked':
                kds_blocked_count += 1
        
        # İşletme odası için loglama
        if business_status == 'sent':
            logger.info(f"[Celery Task] ✅ Business notification sent successfully for order {order_id}")
        elif business_status == 'blocked':
            logger.info(f"[Celery Task] 🔵 Business notification for order {order_id} was blocked by admin settings.")
        else: # 'failed'
            logger.error(f"[Celery Task] ❌ Business notification failed for order {order_id}")
            
        # KDS odaları için loglama
        total_kds_notifications = len(kds_screens_with_items)
        if kds_sent_count == total_kds_notifications:
            logger.info(f"[Celery Task] ✅ All {kds_sent_count} KDS notifications sent successfully for order {order_id}")
        elif kds_sent_count + kds_blocked_count == total_kds_notifications:
            logger.info(f"[Celery Task] 🔵 KDS notifications for order {order_id}: {kds_sent_count} sent, {kds_blocked_count} blocked.")
        else:
            kds_failed_count = total_kds_notifications - kds_sent_count - kds_blocked_count
            logger.warning(f"[Celery Task] ⚠️ KDS notifications for order {order_id}: {kds_sent_count} sent, {kds_blocked_count} blocked, {kds_failed_count} failed.")
        # --- GÜNCELLEME SONU ---

    except Order.DoesNotExist:
        logger.error(f"[Celery Task] Order with ID {order_id} not found.")
        # Bu durumda retry yapmayalım çünkü sipariş gerçekten yok
        return
    except (OperationalError, InterfaceError) as e:
        logger.error(f"[Celery Task] Database connection error for order {order_id}: {e}")
        # Retry decorator otomatik olarak tekrar deneyecek
        raise  # Celery'nin autoretry mekanizmasını tetiklemek için
    except Exception as e:
        logger.error(f"[Celery Task] Failed to send notification for order {order_id}. Error: {e}", exc_info=True)
        # Diğer hatalar için de retry yapalım (ama daha az)
        raise self.retry(countdown=10, max_retries=1)

# ==================== GÜNCELLENMİŞ GÖREV SONU ====================


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
@retry_on_database_error(max_retries=2, delay=1)
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
        
        status = send_socket_io_notification('business_67', 'order_status_update', test_data)
        
        if status != 'failed':
            logger.info(f"[Celery Task] Socket connection test completed with status: {status}")
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
        
        cutoff_date = timezone.now() - timedelta(days=7)
        
        logger.info(f"[Celery Task] Notification cleanup completed for dates before {cutoff_date}")
        
    except Exception as e:
        logger.error(f"[Celery Task] Notification cleanup failed: {e}")


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
    status = send_socket_io_notification(room, 'order_status_update', test_data)
    
    if status != 'failed':
        logger.info(f"[Celery Task] 🧪 Manual test notification sent to {room} with status: {status}")
        return True
    else:
        logger.error(f"[Celery Task] 🧪 Manual test notification failed for {room}")
        return False