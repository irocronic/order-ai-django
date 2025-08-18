# core/signals/order_signals.py

from django.db.models.signals import pre_delete
from django.dispatch import receiver
from asgiref.sync import async_to_sync
import logging
from decimal import Decimal
import uuid
from datetime import datetime, timedelta

from ..models import (
    Order, OrderItem, Pager, NOTIFICATION_EVENT_TYPES,
)
from ..serializers import OrderSerializer

logger = logging.getLogger(__name__)

# --- YARDIMCI FONKSİYONLAR ---

def convert_decimals_to_strings(obj):
    if isinstance(obj, list):
        return [convert_decimals_to_strings(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return str(obj)
    return obj

def serialize_order(order):
    """Order nesnesini serialize eder"""
    return OrderSerializer(order).data

def get_event_type_from_status(order: Order, created: bool, update_fields=None, item_added_info=None) -> str:
    if item_added_info:
        return NOTIFICATION_EVENT_TYPES[15][0]  # 'order_item_added'

    status = order.status
    if created and status == Order.STATUS_APPROVED:
        return NOTIFICATION_EVENT_TYPES[4][0]  # 'order_approved_for_kitchen'
    
    if (created or (update_fields and 'status' in update_fields)) and status == Order.STATUS_PENDING_APPROVAL:
        return NOTIFICATION_EVENT_TYPES[0][0]  # 'guest_order_pending_approval'
        
    if update_fields and 'status' in update_fields:
        status_map = {
            Order.STATUS_APPROVED: NOTIFICATION_EVENT_TYPES[4][0],
            Order.STATUS_PREPARING: NOTIFICATION_EVENT_TYPES[5][0],
            Order.STATUS_READY_FOR_PICKUP: NOTIFICATION_EVENT_TYPES[6][0],
            Order.STATUS_READY_FOR_DELIVERY: NOTIFICATION_EVENT_TYPES[8][0],
            Order.STATUS_COMPLETED: NOTIFICATION_EVENT_TYPES[11][0],
            Order.STATUS_CANCELLED: NOTIFICATION_EVENT_TYPES[12][0],
            Order.STATUS_REJECTED: NOTIFICATION_EVENT_TYPES[13][0],
        }
        return status_map.get(status, NOTIFICATION_EVENT_TYPES[14][0])

    return NOTIFICATION_EVENT_TYPES[14][0]

# GLOBAL DEDUPLİKASYON SİSTEMİ
_sent_notifications = {}
_cleanup_time = None

def _cleanup_old_notifications():
    """Eski notification kayıtlarını temizle"""
    global _sent_notifications, _cleanup_time
    now = datetime.now()
    
    # Her 30 saniyede bir temizlik yap
    if _cleanup_time is None or (now - _cleanup_time).seconds > 30:
        cutoff_time = now - timedelta(seconds=10)  # 10 saniyeden eski olanları sil
        old_keys = [k for k, v in _sent_notifications.items() if v < cutoff_time]
        for key in old_keys:
            del _sent_notifications[key]
        _cleanup_time = now
        if old_keys:
            logger.info(f"[DEDUPLİKASYON] {len(old_keys)} eski notification kaydı temizlendi")

# ==================== GÜNCELLENEN FONKSİYON BAŞLANGICI ====================
def emit_order_status_update(order, event_type, message):
    """
    Sipariş durumu güncellemelerini tek bir mesajla gönderen fonksiyon.
    Düzeltilmiş deduplikasyon mantığı içerir.
    """
    # Eski kayıtları temizle
    _cleanup_old_notifications()
    
    # Benzersiz bir bildirim ID'si oluştur
    notification_id = f"{uuid.uuid4()}-{int(datetime.now().timestamp())}"
    
    # Deduplication key'i artık daha genel ve sadece anlık çift gönderimleri engellemek için.
    # Zaman aralığına bağlı değil, sadece son gönderim zamanına bakıyor.
    dedup_key = f"order_{order.id}_{event_type}"
    
    now = datetime.now()
    
    # Eğer aynı sipariş ve olay türü için 1 saniyeden daha kısa süre önce bildirim gönderildiyse, atla.
    if dedup_key in _sent_notifications and (now - _sent_notifications[dedup_key]).total_seconds() < 1:
        logger.info(f"[DEDUPLİKASYON] SKIPPED (Hızlı Tekrar): {event_type} (Order: {order.id})")
        return
    
    # Bu bildirim'i gönderildi olarak işaretle (yeni zaman damgasıyla)
    _sent_notifications[dedup_key] = now
    
    logger.info(f"[DEDUPLİKASYON] GÖNDERİLİYOR: {event_type} (Order: {order.id}, Notification: {notification_id})")
    
    update_data = {
        'notification_id': notification_id,
        'event_type': event_type,
        'message': message,
        'order_id': order.id,
        'updated_order_data': serialize_order(order),
        'table_number': order.table.table_number if order.table else None,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        from makarna_project.asgi import sio
        if sio is None: 
            return
    except ImportError:
        logger.error("BİLDİRİM GÖNDERME HATASI: sio import edilemedi!")
        return

    business_id = order.business_id
    
    # KDS bilgilerini topla
    kds_screens_with_items = {
        item.menu_item.category.assigned_kds
        for item in order.order_items.all()
        if item.menu_item and item.menu_item.category and item.menu_item.category.assigned_kds
    }

    rooms_to_notify = []
    
    # 1. Business room'u ekle
    business_room = f'business_{business_id}'
    rooms_to_notify.append({
        'room': business_room,
        'data': update_data.copy()
    })
    
    # 2. KDS room'ları ekle (eğer varsa)
    if kds_screens_with_items:
        for kds in kds_screens_with_items:
            kds_room = f'kds_{business_id}_{kds.slug}'
            kds_data = update_data.copy()
            kds_data['kds_slug'] = kds.slug
            rooms_to_notify.append({
                'room': kds_room,
                'data': kds_data
            })
    
    # Her room için ayrı ayrı emit et
    for room_info in rooms_to_notify:
        room_name = room_info['room']
        room_data = room_info['data']
        
        logger.info(f"[DEDUPLİKASYON] -> Room: {room_name}")
        async_to_sync(sio.emit)('order_status_update', convert_decimals_to_strings(room_data), room=room_name)
    
    logger.info(f"[DEDUPLİKASYON] Tamamlandı: {len(rooms_to_notify)} room'a gönderildi")
# ==================== GÜNCELLENEN FONKSİYON SONU ====================

def send_order_update_notification(order, created: bool = False, update_fields=None, item_added_info=None):
    """
    Sipariş güncellemelerini ilgili WebSocket odalarına gönderen merkezi fonksiyon.
    Artık Order nesnesini doğrudan alır, order_id yerine.
    """
    if not isinstance(order, Order):
        logger.error(f"BİLDİRİM GÖNDERME HATASI: Geçersiz 'order' nesnesi tipi. Beklenen: Order, Gelen: {type(order)}")
        return
        
    order_id = order.id
    business_id = order.business_id
    event_type = get_event_type_from_status(order, created, update_fields, item_added_info)
    message = f"Sipariş #{order_id} durumu güncellendi: {order.get_status_display()}"

    if item_added_info:
        message = f"{item_added_info['item_name']} ürünü Sipariş #{order_id}'e eklendi."

    # Yeni deduplication sistemi ile fonksiyonu çağır
    emit_order_status_update(order, event_type, message)

@receiver(pre_delete, sender=Order)
def handle_order_deletion_notification(sender, instance: Order, **kwargs):
    business_id = instance.business_id
    if not business_id:
        return

    try:
        from makarna_project.asgi import sio
        if sio is None: return
    except ImportError:
        return

    general_room_name = f'business_{business_id}'
    payload = {
        'notification_id': f"{uuid.uuid4()}-{int(datetime.now().timestamp())}",
        'event_type': NOTIFICATION_EVENT_TYPES[12][0], # 'order_cancelled_update'
        'order_id': instance.id,
        'table_id': instance.table.id if instance.table else None,
        'message': f"Sipariş #{instance.id} iptal edildi.",
        'timestamp': datetime.now().isoformat()
    }
    logger.info(f"--> [CANCEL/DELETE] Genel Bildirim: Oda: {general_room_name}, Event: {payload['event_type']}, Sipariş ID: {instance.id}")
    async_to_sync(sio.emit)('order_status_update', payload, room=general_room_name)
    
    kds_slugs_to_notify = {
        item.menu_item.category.assigned_kds.slug
        for item in instance.order_items.select_related('menu_item__category__assigned_kds').all()
        if item.menu_item and item.menu_item.category and item.menu_item.category.assigned_kds
    }

    for slug in kds_slugs_to_notify:
        kds_room_name = f'kds_{business_id}_{slug}'
        kds_payload = {**payload, 'kds_slug': slug}
        logger.info(f"--> [CANCEL/DELETE] KDS Bildirimi: Oda: {kds_room_name}, Event: {kds_payload['event_type']}")
        async_to_sync(sio.emit)('order_status_update', kds_payload, room=kds_room_name)

@receiver(pre_delete, sender=Order)
def handle_order_pre_delete_for_pager(sender, instance: Order, **kwargs):
    try:
        if hasattr(instance, 'assigned_pager_instance') and instance.assigned_pager_instance:
            pager_to_free = instance.assigned_pager_instance
            logger.info(f"SİNYAL (Order Pre-Delete): Sipariş #{instance.id} siliniyor. Pager #{pager_to_free.id} ilişkisi SET_NULL ile kaldırılacak.")
    except Pager.DoesNotExist:
        pass
    except AttributeError:
        pass