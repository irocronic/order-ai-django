# makarna_project/core/signals/order_signals.py

from django.db.models.signals import pre_delete, post_save
from django.dispatch import receiver
import logging
from datetime import datetime
import uuid

from ..models import (
    Order, OrderItem, Pager, NOTIFICATION_EVENT_TYPES,
)
from ..tasks import send_order_update_task

logger = logging.getLogger(__name__)


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


# === YENİ EKLENMİŞ: Order post_save signal handler ===
@receiver(post_save, sender=Order)
def order_status_changed_handler(sender, instance, created, update_fields=None, **kwargs):
    """
    Order modeli kaydedildiğinde bildirim gönder
    """
    try:
        # Yeni sipariş oluşturuldu
        if created:
            if instance.status == Order.STATUS_PENDING_APPROVAL:
                if instance.customer is None:
                    # Misafir siparişi
                    event_type = 'guest_order_pending_approval'
                    message = f'Yeni misafir siparişi #{instance.id} onay bekliyor'
                else:
                    # Kayıtlı kullanıcı siparişi
                    event_type = 'order_pending_approval' 
                    message = f'Yeni sipariş #{instance.id} onay bekliyor'
            elif instance.status == Order.STATUS_APPROVED:
                event_type = 'order_approved_for_kitchen'
                message = f'Sipariş #{instance.id} mutfağa gönderildi'
            else:
                return  # Diğer durumlar için bildirim gönderme
        else:
            # Mevcut sipariş güncellendi
            if not update_fields:
                return
                
            if 'status' in update_fields:
                if instance.status == Order.STATUS_APPROVED:
                    event_type = 'order_approved_for_kitchen'
                    message = f'Sipariş #{instance.id} onaylandı - mutfağa gönderildi'
                elif instance.status == Order.STATUS_PREPARING:
                    event_type = 'order_preparing_update'
                    message = f'Sipariş #{instance.id} hazırlanıyor'
                elif instance.status == Order.STATUS_READY_FOR_PICKUP:
                    event_type = 'order_ready_for_pickup_update'
                    message = f'Sipariş #{instance.id} hazır - garson bekleniyor'
                elif instance.status == Order.STATUS_COMPLETED:
                    event_type = 'order_completed_update'
                    message = f'Sipariş #{instance.id} tamamlandı'
                elif instance.status == Order.STATUS_CANCELLED:
                    event_type = 'order_cancelled_update'
                    message = f'Sipariş #{instance.id} iptal edildi'
                else:
                    return
            else:
                return

        # Async task'ı çağır
        logger.info(f"[Order Signal] Sending notification: {event_type} for order {instance.id}")
        send_order_update_task.delay(
            order_id=instance.id,
            event_type=event_type,
            message=message,
            extra_data={
                'status': instance.status,
                'created': created,
                'update_fields': list(update_fields) if update_fields else []
            }
        )
        
    except Exception as e:
        logger.error(f"[Order Signal] Error sending notification for order {instance.id}: {e}")


# === MEVCUT LOGLAMA FONKSİYONU GÜNCELLEME ===
def send_order_update_notification(order, created: bool = False, update_fields=None, item_added_info=None, specific_event_type=None):
    if not isinstance(order, Order):
        logger.error(f"BİLDİRİM GÖNDERME HATASI: Geçersiz 'order' nesnesi tipi. Beklenen: Order, Gelen: {type(order)}")
        return
    
    # === GÜNCELLEME: Eğer post_save signal tetiklenmişse, task'i oradan gönderelim ===
    # Bu fonksiyon artık manual çağrımlar için kullanılacak
    logger.critical(
        f"[send_order_update_notification DEBUG] Order ID: {order.id}, "
        f"Gelen Order Status: '{order.status}', "
        f"Gelen update_fields: {update_fields}, "
        f"Gelen specific_event_type: '{specific_event_type}'"
    )
    
    if specific_event_type:
        event_type = specific_event_type
    else:
        event_type = get_event_type_from_status(order, created, update_fields, item_added_info)
    
    logger.critical(
        f"[send_order_update_notification SONUÇ] Order ID: {order.id}, "
        f"Üretilen Event Type: '{event_type}'"
    )

    message = f"Sipariş #{order.id} durumu güncellendi: {order.get_status_display()}"

    if item_added_info:
        message = f"{item_added_info['item_name']} ürünü Sipariş #{order.id}'e eklendi."
    
    send_order_update_task.delay(order_id=order.id, event_type=event_type, message=message)
    logger.info(f"Celery task for order #{order.id} (Event: {event_type}) has been queued.")


@receiver(pre_delete, sender=Order)
def handle_order_deletion_notification(sender, instance: Order, **kwargs):
    send_order_update_task.delay(
        order_id=instance.id,
        event_type='order_cancelled_update',
        message=f"Sipariş #{instance.id} iptal edildi."
    )

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