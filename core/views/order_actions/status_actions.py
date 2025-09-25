# core/views/order_actions/status_actions.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from django.db import transaction
import logging
from decimal import Decimal
from asgiref.sync import async_to_sync

# Gerekli importlar eklendi
from makarna_project.asgi import sio
from ...utils.json_helpers import convert_decimals_to_strings
from ...models import Order, OrderItem
from ...serializers import OrderSerializer
from ...utils.order_helpers import PermissionKeys

logger = logging.getLogger(__name__)

@transaction.atomic
def approve_guest_order_action(view_instance, request, pk=None):
    """Misafir siparişini onaylar ve detaylı bildirim gönderir."""
    order = view_instance.get_object()
    user = request.user

    if not (user.user_type == 'business_owner' or
            (user.user_type == 'staff' and PermissionKeys.TAKE_ORDERS in user.staff_permissions)):
        raise PermissionDenied("Bu siparişi onaylama yetkiniz yok.")

    if order.status != Order.STATUS_PENDING_APPROVAL:
        return Response({'detail': 'Bu sipariş zaten onaylanmış veya farklı bir durumda.'}, status=status.HTTP_400_BAD_REQUEST)

    order.status = Order.STATUS_APPROVED
    order.taken_by_staff = user
    order.approved_at = timezone.now()
    order.save(update_fields=['status', 'taken_by_staff', 'approved_at'])

    updated_item_count = order.order_items.filter(is_awaiting_staff_approval=True).update(is_awaiting_staff_approval=False)
    logger.info(f"Sipariş #{order.id} kullanıcı {user.username} tarafından ONAYLANDI. {updated_item_count} kalem onaylandı.")

    order.refresh_from_db()
    
    order_serializer = OrderSerializer(order, context={'request': request})

    # === GÜNCELLEME: Sinyal yerine doğrudan Socket.IO event'i gönderiliyor ===
    def send_socket_notification():
        if sio:
            room_name = f'business_{order.business.id}'
            table_info = f"Masa {order.table.table_number}" if order.table else order.get_order_type_display()
            payload = {
                'event_type': 'order_approved_for_kitchen',
                'message_key': 'notificationOrderApprovedForKitchen',
                'message_args': {
                    'orderId': str(order.id),
                    'tableInfo': table_info
                },
                'updated_order_data': convert_decimals_to_strings(order_serializer.data),
            }
            try:
                async_to_sync(sio.emit)('order_status_update', payload, room=room_name)
                logger.info(f"Socket.IO 'order_approved_for_kitchen' event for Order ID {order.id} sent.")
            except Exception as e:
                logger.error(f"Socket.IO emit error in approve_guest_order_action: {e}")

    transaction.on_commit(send_socket_notification)
    
    return Response(order_serializer.data, status=status.HTTP_200_OK)


@transaction.atomic
def reject_guest_order_action(view_instance, request, pk=None):
    """Misafir siparişini reddeder ve detaylı bildirim gönderir."""
    order = view_instance.get_object()
    user = request.user

    if not (user.user_type == 'business_owner' or
            (user.user_type == 'staff' and PermissionKeys.TAKE_ORDERS in user.staff_permissions)):
        raise PermissionDenied("Bu siparişi reddetme yetkiniz yok.")

    if order.status != Order.STATUS_PENDING_APPROVAL:
        return Response({'detail': 'Bu siparişin durumu zaten değiştirilmiş.'}, status=status.HTTP_400_BAD_REQUEST)
    
    items_to_delete_if_modification_rejected = order.order_items.filter(is_awaiting_staff_approval=True)
    previously_approved_items_exist = order.order_items.filter(is_awaiting_staff_approval=False).exists()

    update_fields = []
    if previously_approved_items_exist and items_to_delete_if_modification_rejected.exists():
        items_to_delete_if_modification_rejected.delete()
        order.status = Order.STATUS_APPROVED
        update_fields.append('status')
        if not order.taken_by_staff:
            order.taken_by_staff = user
            update_fields.append('taken_by_staff')
        if not order.approved_at:
            order.approved_at = timezone.now()
            update_fields.append('approved_at')
        order.save(update_fields=update_fields)
    else:
        order.status = Order.STATUS_REJECTED
        order.taken_by_staff = user
        update_fields.extend(['status', 'taken_by_staff'])
        order.save(update_fields=update_fields)

    order.refresh_from_db()
    order_serializer = OrderSerializer(order, context={'request': request})
    
    # === GÜNCELLEME: Sinyal yerine doğrudan Socket.IO event'i gönderiliyor ===
    def send_socket_notification():
        if sio:
            room_name = f'business_{order.business.id}'
            payload = {
                'event_type': 'order_rejected_update',
                'message_key': 'notificationOrderRejected',
                'message_args': {'orderId': str(order.id)},
                'updated_order_data': convert_decimals_to_strings(order_serializer.data),
            }
            try:
                async_to_sync(sio.emit)('order_status_update', payload, room=room_name)
                logger.info(f"Socket.IO 'order_rejected_update' event for Order ID {order.id} sent.")
            except Exception as e:
                logger.error(f"Socket.IO emit error in reject_guest_order_action: {e}")

    transaction.on_commit(send_socket_notification)
    
    return Response(order_serializer.data, status=status.HTTP_200_OK)


@transaction.atomic
def mark_order_picked_up_by_waiter_action(view_instance, request, pk=None):
    """Siparişi garson tarafından mutfaktan alınmış olarak işaretler ve detaylı bildirim gönderir."""
    order = view_instance.get_object()
    user = request.user

    if not (user.user_type == 'business_owner' or \
            (user.user_type == 'staff' and PermissionKeys.TAKE_ORDERS in user.staff_permissions)):
        raise PermissionDenied("Siparişi mutfaktan alma yetkiniz yok.")

    if order.status != Order.STATUS_READY_FOR_PICKUP:
        return Response(
            {'detail': f"Bu siparişin durumu '{order.get_status_display()}', mutfaktan alınmaya uygun değil."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    order.status = Order.STATUS_READY_FOR_DELIVERY
    order.picked_up_by_waiter_at = timezone.now()
    order.save(update_fields=['status', 'picked_up_by_waiter_at'])
    logger.info(f"Sipariş #{order.id} garson {user.username} tarafından mutfaktan alındı ve durumu '{Order.STATUS_READY_FOR_DELIVERY}' olarak güncellendi.")

    order.refresh_from_db()
    order_serializer = OrderSerializer(order, context={'request': request})
    
    # === GÜNCELLEME: Sinyal yerine doğrudan Socket.IO event'i gönderiliyor ===
    def send_socket_notification():
        if sio:
            room_name = f'business_{order.business.id}'
            payload = {
                'event_type': 'order_picked_up_by_waiter',
                'message_key': 'notificationOrderPickedUpByWaiter',
                'message_args': {'orderId': str(order.id)},
                'updated_order_data': convert_decimals_to_strings(order_serializer.data),
            }
            try:
                async_to_sync(sio.emit)('order_status_update', payload, room=room_name)
                logger.info(f"Socket.IO 'order_picked_up_by_waiter' event for Order ID {order.id} sent.")
            except Exception as e:
                logger.error(f"Socket.IO emit error in mark_order_picked_up_by_waiter_action: {e}")
    
    transaction.on_commit(send_socket_notification)

    return Response(order_serializer.data, status=status.HTTP_200_OK)


@transaction.atomic
def deliver_all_items_action(view_instance, request, pk=None):
    """Siparişin tüm kalemlerini müşteriye teslim edilmiş olarak işaretler ve detaylı bildirim gönderir."""
    order = view_instance.get_object()
    if order.is_paid or order.status in [Order.STATUS_COMPLETED, Order.STATUS_CANCELLED, Order.STATUS_REJECTED]:
        raise PermissionDenied("Bu sipariş üzerinde işlem yapılamaz.")
    user = request.user

    if not (user.user_type == 'business_owner' or
            (user.user_type == 'staff' and PermissionKeys.TAKE_ORDERS in user.staff_permissions)):
        raise PermissionDenied("Siparişin tamamını teslim etme yetkiniz yok.")

    if order.status not in [Order.STATUS_READY_FOR_DELIVERY, Order.STATUS_READY_FOR_PICKUP]:
        return Response(
            {'detail': f"Bu sipariş müşteriye teslim edilmeye hazır değil. Durum: {order.get_status_display()}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if order.delivered_at is not None:
        logger.info(f"[DELIVER_ORDER_ALL] Order ID {order.id} was already delivered at {order.delivered_at}. Returning success.")
        return Response(OrderSerializer(order, context={'request': request}).data, status=status.HTTP_200_OK)

    now = timezone.now()
    order.delivered_at = now
    updated_item_count = order.order_items.filter(delivered=False).update(delivered=True)
    logger.info(f"[DELIVER_ORDER_ALL] {updated_item_count} items in Order ID {order.id} marked as delivered.")
    order.save(update_fields=['delivered_at'])
    logger.info(f"[DELIVER_ORDER_ALL] Order ID {order.id} marked as delivered at {now}.")

    order.refresh_from_db()
    order_serializer = OrderSerializer(order, context={'request': request})

    # === GÜNCELLEME: Sinyal yerine doğrudan Socket.IO event'i gönderiliyor ===
    def send_socket_notification():
        if sio:
            room_name = f'business_{order.business.id}'
            payload = {
                'event_type': 'order_fully_delivered',
                'message_key': 'notificationOrderFullyDelivered',
                'message_args': {'orderId': str(order.id)},
                'updated_order_data': convert_decimals_to_strings(order_serializer.data),
            }
            try:
                async_to_sync(sio.emit)('order_status_update', payload, room=room_name)
                logger.info(f"Socket.IO 'order_fully_delivered' event for Order ID {order.id} sent.")
            except Exception as e:
                logger.error(f"Socket.IO emit error in deliver_all_items_action: {e}")

    transaction.on_commit(send_socket_notification)

    return Response(order_serializer.data, status=status.HTTP_200_OK)