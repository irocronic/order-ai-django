# core/tasks.py

from celery import shared_task
from asgiref.sync import async_to_sync
from decimal import Decimal
import logging
from .models import Order
from .serializers import OrderSerializer
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

def _convert_decimals_to_strings(obj):
    if isinstance(obj, list):
        return [_convert_decimals_to_strings(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _convert_decimals_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return str(obj)
    return obj

@shared_task(name="send_order_update_notification")
def send_order_update_task(order_id, event_type, message, extra_data=None):
    """
    WebSocket üzerinden sipariş güncelleme bildirimini gönderen Celery task'i.
    """
    logger.info(f"[Celery Task] Sending notification for Order ID: {order_id}, Event: {event_type}")
    try:
        from makarna_project.asgi import sio

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
            'updated_order_data': _convert_decimals_to_strings(serialized_order),
            'table_number': order.table.table_number if order.table else None,
            'timestamp': datetime.now().isoformat()
        }
        if extra_data:
            update_data.update(extra_data)

        # İlgili odaları belirle
        business_room = f"business_{order.business_id}"
        
        kds_screens_with_items = {
            item.menu_item.category.assigned_kds
            for item in order.order_items.all()
            if item.menu_item and item.menu_item.category and item.menu_item.category.assigned_kds
        }

        # Business room'a gönder
        async_to_sync(sio.emit)('order_status_update', update_data, room=business_room)
        logger.info(f"[Celery Task] Notification sent to room: {business_room}")

        # KDS room'larına gönder
        for kds in kds_screens_with_items:
            kds_room = f"kds_{order.business_id}_{kds.slug}"
            kds_data = update_data.copy()
            kds_data['kds_slug'] = kds.slug
            async_to_sync(sio.emit)('order_status_update', kds_data, room=kds_room)
            logger.info(f"[Celery Task] Notification sent to KDS room: {kds_room}")
    
    except Order.DoesNotExist:
        logger.error(f"[Celery Task] Order with ID {order_id} not found.")
    except Exception as e:
        logger.error(f"[Celery Task] Failed to send notification for order {order_id}. Error: {e}", exc_info=True)
        # Hata durumunda görevi yeniden denemek için: self.retry(exc=e, countdown=60)