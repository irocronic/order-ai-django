# core/tasks.py - GÜVENLİ VERSİYON (Memory Leak Koruması Eklenmiş)

from celery import shared_task
from django.conf import settings
import logging
from urllib.parse import urlparse
import redis
import json
from django.core.mail import send_mail
import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from socket import timeout as SocketTimeout
import weakref
import gc

from .models import Order, Ingredient, Supplier
from .serializers import OrderSerializer
import uuid
from datetime import datetime
from .utils.json_helpers import convert_decimals_to_strings
from .utils.notification_gate import is_notification_active

logger = logging.getLogger(__name__)

# Redis istemcisini kurma
try:
    url = urlparse(settings.REDIS_URL)
    redis_opts = {
        'host': url.hostname,
        'port': url.port,
        'ssl': url.scheme == 'rediss',
        'ssl_cert_reqs': None,
        'decode_responses': False,
    }
    if url.password:
        redis_opts['password'] = url.password

    redis_client = redis.Redis(**redis_opts)
    logger.info("Redis client successfully initialized.")
    
except Exception as e:
    logger.error(f"Failed to initialize Redis client: {e}")
    redis_client = None

# Memory leak koruması için connection havuzu
_connection_pool = weakref.WeakValueDictionary()

def cleanup_connections():
    """Kullanılmayan bağlantıları temizle"""
    try:
        gc.collect()  # Garbage collector'ı çalıştır
        logger.debug(f"Connection cleanup completed. Pool size: {len(_connection_pool)}")
    except Exception as e:
        logger.error(f"Connection cleanup error: {e}")

async def safe_emit_notification(sio, event, data, room):
    """Memory leak koruması ile Socket.IO emit"""
    connection_ref = None
    try:
        # Connection timeout ayarla
        await asyncio.wait_for(sio.emit(event, data, room=room), timeout=5.0)
        logger.info(f"[Notification] Successfully sent to room: {room}")
        return True
    except asyncio.TimeoutError:
        logger.warning(f"[Notification] Timeout while sending to room: {room}")
        return False
    except Exception as e:
        logger.error(f"[Notification] Error sending to room {room}: {e}")
        return False
    finally:
        # Connection cleanup
        if connection_ref:
            try:
                connection_ref.close()
            except:
                pass
        cleanup_connections()

def send_socket_io_notification(room, event, data):
    """
    Socket.IO bildirimi gönderen yardımcı fonksiyon.
    Memory leak koruması ve connection cleanup ile
    Dönüş değerleri: 'sent', 'blocked', 'failed'
    """
    event_type_to_check = data.get('event_type')
    
    if event_type_to_check and event_type_to_check != 'test_notification':
        if not is_notification_active(event_type_to_check):
            logger.info(f"[Notification Gate] Bildirim engellendi (pasif): {event_type_to_check}")
            return 'blocked'

    success = False
    
    try:
        from makarna_project.asgi import sio
        
        async def emit_notification_with_cleanup():
            connection = None
            try:
                # Connection ile işlem yap
                success = await safe_emit_notification(sio, event, data, room)
                return success
            except Exception as e:
                logger.error(f"[Notification] Emit with cleanup failed: {e}")
                return False
            finally:
                # Her durumda cleanup yap
                if connection:
                    try:
                        await connection.disconnect()
                    except:
                        pass
                cleanup_connections()
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Yeni event loop task'ı oluştur ve cleanup'ı garanti et
                task = asyncio.create_task(emit_notification_with_cleanup())
                # Task completion callback ile cleanup
                task.add_done_callback(lambda t: cleanup_connections())
            else:
                success = loop.run_until_complete(emit_notification_with_cleanup())
        except RuntimeError:
            success = asyncio.run(emit_notification_with_cleanup())
            
        if success:
            logger.info(f"[Notification] Sent via Socket.IO server to room: {room}")
        
    except Exception as e:
        logger.error(f"[Notification] Direct Socket.IO emit failed: {e}")
    finally:
        # Her durumda cleanup yap
        cleanup_connections()
    
    if not success and redis_client:
        redis_connection = None
        try:
            message = {
                "uid": "emitter",
                "type": 2,
                "data": [event, data],
                "nsp": "/"
            }
            room_key = f"socket.io#{room}"
            redis_connection = redis_client
            redis_connection.publish(room_key, json.dumps(message))
            logger.info(f"[Notification] Sent via Redis pub/sub to room: {room}")
            success = True
            
        except Exception as e:
            logger.error(f"[Notification] Redis pub/sub failed: {e}")
        finally:
            # Redis connection cleanup
            if redis_connection and hasattr(redis_connection, 'connection_pool'):
                try:
                    redis_connection.connection_pool.disconnect()
                except:
                    pass
    
    if not success:
        http_session = None
        try:
            import requests
            webhook_url = "https://order-ai-7bd2c97ec9ef.herokuapp.com/api/webhook/socket-emit/"
            payload = {
                'room': room,
                'event': event,
                'data': data
            }
            
            # Session ile bağlantı havuzunu yönet
            http_session = requests.Session()
            response = http_session.post(webhook_url, json=payload, timeout=5)
            
            if response.status_code == 200:
                logger.info(f"[Notification] Sent via HTTP webhook to room: {room}")
                success = True
            else:
                logger.debug(f"[Notification] HTTP webhook not available: {response.status_code}")
                
        except Exception as e:
            logger.debug(f"[Notification] HTTP webhook not available: {e}")
        finally:
            # HTTP session cleanup
            if http_session:
                try:
                    http_session.close()
                except:
                    pass
    
    # Final cleanup
    cleanup_connections()
    return 'sent' if success else 'failed'


@shared_task(name="send_order_update_notification")
def send_order_update_task(order_id, event_type, message, extra_data=None):
    """
    WebSocket üzerinden sipariş güncelleme bildirimini gönderen Celery task'i.
    Memory leak koruması ile
    """
    logger.info(f"[Celery Task] Sending notification for Order ID: {order_id}, Event: {event_type}")
    
    order = None
    serialized_order = None
    
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
        
        if business_status == 'sent':
            logger.info(f"[Celery Task] ✅ Business notification sent successfully for order {order_id}")
        elif business_status == 'blocked':
            logger.info(f"[Celery Task] 🔵 Business notification for order {order_id} was blocked by admin settings.")
        else:
            logger.error(f"[Celery Task] ❌ Business notification failed for order {order_id}")
            
        total_kds_notifications = len(kds_screens_with_items)
        if kds_sent_count == total_kds_notifications:
            logger.info(f"[Celery Task] ✅ All {kds_sent_count} KDS notifications sent successfully for order {order_id}")
        elif kds_sent_count + kds_blocked_count == total_kds_notifications:
            logger.info(f"[Celery Task] 🔵 KDS notifications for order {order_id}: {kds_sent_count} sent, {kds_blocked_count} blocked.")
        else:
            kds_failed_count = total_kds_notifications - kds_sent_count - kds_blocked_count
            logger.warning(f"[Celery Task] ⚠️ KDS notifications for order {order_id}: {kds_sent_count} sent, {kds_blocked_count} blocked, {kds_failed_count} failed.")

    except Order.DoesNotExist:
        logger.error(f"[Celery Task] Order with ID {order_id} not found.")
        raise
    except Exception as e:
        logger.error(f"[Celery Task] Failed to send notification for order {order_id}. Error: {e}", exc_info=True)
        raise
    finally:
        # Memory cleanup
        order = None
        serialized_order = None
        cleanup_connections()
        gc.collect()


@shared_task(name="send_bulk_order_notifications")
def send_bulk_order_notifications(notification_list):
    """
    Toplu sipariş bildirimlerini gönderen task
    """
    try:
        for notification in notification_list:
            send_order_update_task.delay(
                notification.get('order_id'),
                notification.get('event_type'),
                notification.get('message'),
                notification.get('extra_data')
            )
    finally:
        cleanup_connections()


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
    finally:
        cleanup_connections()


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
    finally:
        cleanup_connections()


@shared_task(name="send_test_notification")
def send_test_notification(business_id=67):
    """
    Manual test bildirimi gönderen task
    """
    try:
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
    finally:
        cleanup_connections()


# ==================== GÜVENLİ E-POSTA SİSTEMİ ====================

async def send_email_async(subject, message, from_email, recipient_list, timeout=10):
    """
    Async e-posta gönderme fonksiyonu - timeout koruması ve connection cleanup ile
    """
    server = None
    try:
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = ', '.join(recipient_list)
        msg['Subject'] = subject
        msg.attach(MIMEText(message, 'plain', 'utf-8'))

        # SMTP ayarlarını Django settings'den al
        smtp_host = getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com')
        smtp_port = getattr(settings, 'EMAIL_PORT', 587)
        smtp_user = getattr(settings, 'EMAIL_HOST_USER', '')
        smtp_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        use_tls = getattr(settings, 'EMAIL_USE_TLS', True)

        # Async SMTP ile gönder
        server = aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port)
        
        # Timeout kontrolü ile bağlantı
        await asyncio.wait_for(server.connect(), timeout=timeout)
        
        if use_tls:
            await asyncio.wait_for(server.starttls(), timeout=timeout)
        
        if smtp_user and smtp_password:
            await asyncio.wait_for(server.login(smtp_user, smtp_password), timeout=timeout)
        
        await asyncio.wait_for(server.send_message(msg), timeout=timeout)
        
        logger.info(f"[Email] ✅ Async e-posta başarıyla gönderildi: {recipient_list}")
        return True
        
    except asyncio.TimeoutError:
        logger.error(f"[Email] ⏰ E-posta gönderimi zaman aşımı ({timeout}s): {recipient_list}")
        return False
    except Exception as e:
        logger.error(f"[Email] ❌ Async e-posta hatası: {e}")
        return False
    finally:
        # SMTP connection cleanup
        if server:
            try:
                await asyncio.wait_for(server.quit(), timeout=2)
            except:
                try:
                    server.close()
                except:
                    pass


def send_email_sync_fallback(subject, message, from_email, recipient_list, timeout=5):
    """
    Sync fallback e-posta gönderme - kısa timeout ile
    """
    import socket
    default_timeout = socket.getdefaulttimeout()
    
    try:
        socket.setdefaulttimeout(timeout)
        
        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=False,
            connection=None
        )
        
        logger.info(f"[Email] ✅ Sync fallback e-posta gönderildi: {recipient_list}")
        return True
        
    except (smtplib.SMTPException, SocketTimeout, OSError) as e:
        logger.error(f"[Email] ❌ Sync fallback e-posta hatası: {e}")
        return False
    finally:
        try:
            socket.setdefaulttimeout(default_timeout)
        except:
            pass


@shared_task(bind=True, name="send_low_stock_email_to_supplier", max_retries=2, default_retry_delay=300)
def send_low_stock_notification_email_task(self, ingredient_id):
    """
    GÜVENLİ VERSİYON: Async + Timeout + Fallback + Retry + WebSocket bildirimi + Memory Leak Koruması
    """
    logger.info(f"[Celery Task] 📧 Düşük stok e-posta bildirimi başlatılıyor. Malzeme ID: {ingredient_id}")
    
    ingredient = None
    
    def format_quantity(value):
        """Sayıları kullanıcı dostu formatta döndürür."""
        if value is None:
            return "0"
        if value == int(value):
            return str(int(value))
        else:
            return f"{value:.3f}".rstrip('0').rstrip('.')
    
    try:
        ingredient = Ingredient.objects.select_related('supplier', 'unit', 'business').get(id=ingredient_id)

        if not ingredient.supplier or not ingredient.supplier.email:
            logger.warning(f"[Email] ⚠️ Malzeme '{ingredient.name}' için tedarikçi/e-posta yok. Atlanıyor.")
            return {"status": "skipped", "reason": "no_supplier_email"}

        supplier = ingredient.supplier
        business = ingredient.business

        # Formatlanmış değerler
        formatted_current_stock = format_quantity(ingredient.stock_quantity)
        formatted_alert_threshold = format_quantity(ingredient.alert_threshold)

        subject = f"Düşük Stok Uyarısı: {ingredient.name} - {business.name}"
        message = f"""
Merhaba {supplier.contact_person or supplier.name},

{business.name} adlı işletmemizde, yönettiğiniz bir ürün için stok seviyesi kritik düzeyin altına düşmüştür.

Malzeme Detayları:
- Malzeme Adı: {ingredient.name}
- Mevcut Stok: {formatted_current_stock} {ingredient.unit.abbreviation}
- Uyarı Eşiği: {formatted_alert_threshold} {ingredient.unit.abbreviation}

Lütfen en kısa sürede yeni bir sevkiyat planlaması için bizimle iletişime geçin.

İşletme Bilgileri:
- İşletme: {business.name}
- Telefon: {business.phone or 'Belirtilmemiş'}

Teşekkürler,
{business.name} Yönetimi
"""
        
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [supplier.email]

        # 1. ÖNCE ASYNC DENEMESİ (10 saniye timeout)
        try:
            logger.info(f"[Email] 🚀 Async e-posta denemesi: {recipient_list}")
            success = asyncio.run(send_email_async(subject, message, from_email, recipient_list, timeout=10))
            
            if success:
                # Bildirim bayrağını işaretle
                ingredient.low_stock_notification_sent = True
                ingredient.save(update_fields=['low_stock_notification_sent'])
                logger.info(f"'{ingredient.name}' için düşük stok bildirim bayrağı True olarak işaretlendi.")

                # Flutter arayüzünü anlık olarak güncellemek için WebSocket bildirimi gönder
                try:
                    business_room = f"business_{ingredient.business_id}"
                    payload = {
                        'event_type': 'ingredient_status_update',
                        'message': f"'{ingredient.name}' için tedarikçiye düşük stok bildirimi gönderildi.",
                        'ingredient_id': ingredient.id,
                        'ingredient_name': ingredient.name,
                        'low_stock_notification_sent': True,
                        'notification_id': f"ingredient_update_{uuid.uuid4()}",
                        'timestamp': datetime.now().isoformat()
                    }
                    send_socket_io_notification(business_room, 'stock_event', payload)
                    logger.info(f"İşletme odasına ({business_room}) anlık stok durumu güncellemesi gönderildi.")
                except Exception as e_socket:
                    logger.error(f"Stok durumu için socket bildirimi gönderilirken hata: {e_socket}")
                
                logger.info(f"[Email] ✅ Async e-posta başarılı: '{ingredient.name}' → {supplier.email}")
                return {"status": "success", "method": "async", "ingredient": ingredient.name}
        
        except Exception as e:
            logger.warning(f"[Email] ⚠️ Async e-posta hatası, fallback deneniyor: {e}")

        # 2. SYNC FALLBACK (5 saniye timeout)
        logger.info(f"[Email] 🔄 Sync fallback e-posta denemesi: {recipient_list}")
        success = send_email_sync_fallback(subject, message, from_email, recipient_list, timeout=5)
        
        if success:
            # Bildirim bayrağını işaretle
            ingredient.low_stock_notification_sent = True
            ingredient.save(update_fields=['low_stock_notification_sent'])
            logger.info(f"'{ingredient.name}' için düşük stok bildirim bayrağı True olarak işaretlendi (fallback).")

            # Flutter arayüzünü anlık olarak güncellemek için WebSocket bildirimi gönder
            try:
                business_room = f"business_{ingredient.business_id}"
                payload = {
                    'event_type': 'ingredient_status_update',
                    'message': f"'{ingredient.name}' için tedarikçiye düşük stok bildirimi gönderildi.",
                    'ingredient_id': ingredient.id,
                    'ingredient_name': ingredient.name,
                    'low_stock_notification_sent': True,
                    'notification_id': f"ingredient_update_{uuid.uuid4()}",
                    'timestamp': datetime.now().isoformat()
                }
                send_socket_io_notification(business_room, 'stock_event', payload)
                logger.info(f"İşletme odasına ({business_room}) anlık stok durumu güncellemesi gönderildi (fallback).")
            except Exception as e_socket:
                logger.error(f"Stok durumu için socket bildirimi gönderilirken hata (fallback): {e_socket}")
            
            logger.info(f"[Email] ✅ Sync fallback e-posta başarılı: '{ingredient.name}' → {supplier.email}")
            return {"status": "success", "method": "sync_fallback", "ingredient": ingredient.name}

        # 3. HER İKİSİ DE BAŞARISIZSA RETRY
        logger.error(f"[Email] ❌ Tüm e-posta yöntemleri başarısız. Retry yapılacak. Malzeme: {ingredient.name}")
        
        # Celery retry mekanizması
        raise self.retry(countdown=300, max_retries=2)

    except Ingredient.DoesNotExist:
        logger.error(f"[Email] ❌ Malzeme ID {ingredient_id} bulunamadı.")
        return {"status": "error", "reason": "ingredient_not_found"}
    
    except self.Retry:
        # Retry exception'ı tekrar fırlat
        raise
    
    except Exception as e:
        logger.error(f"[Email] ❌ Kritik e-posta hatası: {e}", exc_info=True)
        
        # Son çare olarak retry
        if self.request.retries < self.max_retries:
            logger.info(f"[Email] 🔄 Son çare retry. Deneme: {self.request.retries + 1}/{self.max_retries}")
            raise self.retry(countdown=600, max_retries=2)
        else:
            logger.error(f"[Email] ❌ Tüm retry denemeleri tükendi. Malzeme ID: {ingredient_id}")
            return {"status": "failed", "reason": "max_retries_exceeded", "ingredient_id": ingredient_id}
    
    finally:
        # Memory cleanup
        ingredient = None
        cleanup_connections()
        gc.collect()


@shared_task(name="send_manual_low_stock_email")
def send_manual_low_stock_email_task(supplier_id, ingredient_ids):
    """
    Belirli bir tedarikçiye, seçilen birden çok malzeme için
    tek bir düşük stok bilgilendirme e-postası gönderir.
    Memory leak koruması ile
    """
    logger.info(f"[Celery Task] 📧 Manuel düşük stok e-posta bildirimi başlatılıyor. Tedarikçi ID: {supplier_id}, Malzeme ID'leri: {ingredient_ids}")

    supplier = None
    ingredients = None

    try:
        supplier = Supplier.objects.get(id=supplier_id)
        ingredients = Ingredient.objects.filter(id__in=ingredient_ids).select_related('unit', 'business')
    except Supplier.DoesNotExist:
        logger.error(f"[Email] ❌ Tedarikçi ID {supplier_id} bulunamadı.")
        return {"status": "error", "reason": "supplier_not_found"}
    finally:
        cleanup_connections()

    if not ingredients.exists():
        logger.warning(f"[Email] ⚠️ E-posta için malzeme bulunamadı. ID'ler: {ingredient_ids}")
        return {"status": "skipped", "reason": "no_ingredients_found"}

    if not supplier.email:
        logger.warning(f"[Email] ⚠️ Tedarikçi '{supplier.name}' için e-posta adresi yok. Atlanıyor.")
        return {"status": "skipped", "reason": "no_supplier_email"}

    business = ingredients.first().business
    
    # E-posta içeriğini oluştur
    ingredient_list_str = ""
    for ing in ingredients:
        stock_qty_str = f"{ing.stock_quantity:.2f}".rstrip('0').rstrip('.')
        threshold_str = f"{ing.alert_threshold:.2f}".rstrip('0').rstrip('.') if ing.alert_threshold else "N/A"
        ingredient_list_str += f"- {ing.name}: Mevcut Stok {stock_qty_str} {ing.unit.abbreviation} (Uyarı Eşiği: {threshold_str})\n"

    subject = f"Malzeme Talebi/Düşük Stok Bildirimi - {business.name}"
    message = f"""
Merhaba {supplier.contact_person or supplier.name},

{business.name} adlı işletmemizden aşağıdaki malzemeler için bir talep/düşük stok bildirimi gönderilmiştir:

{ingredient_list_str}
Lütfen en kısa sürede yeni bir sevkiyat planlaması için bizimle iletişime geçin.

İşletme Bilgileri:
- İşletme: {business.name}
- Telefon: {business.phone or 'Belirtilmemiş'}

Teşekkürler,
{business.name} Yönetimi
"""

    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [supplier.email]

    try:
        # E-postayı gönder
        success_async = asyncio.run(send_email_async(subject, message, from_email, recipient_list))
        if not success_async:
            logger.warning("[Email] ⚠️ Manuel e-posta async gönderimi başarısız, fallback deneniyor.")
            send_email_sync_fallback(subject, message, from_email, recipient_list)
        
        return {"status": "success", "supplier": supplier.name}
    
    except Exception as e:
        logger.error(f"[Email] ❌ Manuel e-posta gönderimi hatası: {e}")
        return {"status": "error", "reason": str(e)}
    
    finally:
        # Memory cleanup
        supplier = None
        ingredients = None
        cleanup_connections()
        gc.collect()