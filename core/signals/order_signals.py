# makarna_project/core/signals/order_signals.py (Güncellendi)

from django.db.models.signals import pre_delete
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


def send_order_update_notification(order, created: bool = False, update_fields=None, item_added_info=None, specific_event_type=None):
    if not isinstance(order, Order):
        logger.error(f"BİLDİRİM GÖNDERME HATASI: Geçersiz 'order' nesnesi tipi. Beklenen: Order, Gelen: {type(order)}")
        return
    
    if specific_event_type:
        event_type = specific_event_type
    else:
        event_type = get_event_type_from_status(order, created, update_fields, item_added_info)
    
    logger.info(
        f"[send_order_update_notification] Order ID: {order.id}, "
        f"Event Type: '{event_type}'"
    )

    # Sadece anahtar gönderiyoruz, çevrilmiş metin veya message yok!
    message_key = 'orderStatusUpdate'
    message_args = {
        'orderId': str(order.id),
        'statusKey': order.status,  # 'approved', 'preparing' gibi ham anahtar
    }

    if item_added_info:
        message_key = 'orderItemAdded'
        message_args = {
            'orderId': str(order.id),
            'itemName': item_added_info.get('item_name', 'Bilinmeyen ürün')
        }

    extra_data = {
        'message_key': message_key,
        'message_args': message_args
    }
    
    # Artık 'message' alanı gönderilmiyor! Flutter localize edecek.
    send_order_update_task.delay(
        order_id=order.id, 
        event_type=event_type, 
        extra_data=extra_data
    )
    logger.info(f"Celery task for order #{order.id} (Event: {event_type}) has been queued with structured data.")


@receiver(pre_delete, sender=Order)
def handle_order_deletion_notification(sender, instance: Order, **kwargs):
    send_order_update_task.delay(
        order_id=instance.id,
        event_type='order_cancelled_update',
        # Burada da message kaldırıldı!
        extra_data={
            'message_key': 'orderCancelled',
            'message_args': {
                'orderId': str(instance.id)
            }
        }
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