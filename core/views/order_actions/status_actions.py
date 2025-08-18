# core/views/order_actions/status_actions.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from django.db import transaction
import logging
from decimal import Decimal

from ...models import Order, OrderItem
from ...serializers import OrderSerializer
from ...utils.order_helpers import PermissionKeys
# <<< GÜNCELLEME: Merkezi bildirim fonksiyonunu import ediyoruz >>>
from ...signals.order_signals import send_order_update_notification

logger = logging.getLogger(__name__)

@transaction.atomic
def approve_guest_order_action(view_instance, request, pk=None):
    """Misafir siparişini onaylar."""
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
    
    # <<< YENİ: Bildirimi doğrudan ve sadece buradan gönderiyoruz >>>
    transaction.on_commit(
        lambda: send_order_update_notification(
            order=order,  # order_id yerine order nesnesi
            created=False, 
            update_fields=['status']
        )
    )
    # <<< GÜNCELLEME SONU >>>
    
    order_serializer = OrderSerializer(order, context={'request': request})
    return Response(order_serializer.data, status=status.HTTP_200_OK)


@transaction.atomic
def reject_guest_order_action(view_instance, request, pk=None):
    """Misafir siparişini reddeder."""
    order = view_instance.get_object()
    user = request.user

    if not (user.user_type == 'business_owner' or
            (user.user_type == 'staff' and PermissionKeys.TAKE_ORDERS in user.staff_permissions)):
        raise PermissionDenied("Bu siparişi reddetme yetkiniz yok.")

    if order.status != Order.STATUS_PENDING_APPROVAL:
        return Response({'detail': 'Bu siparişin durumu zaten değiştirilmiş.'}, status=status.HTTP_400_BAD_REQUEST)
    
    items_to_delete_if_modification_rejected = order.order_items.filter(is_awaiting_staff_approval=True)
    previously_approved_items_exist = order.order_items.filter(is_awaiting_staff_approval=False).exists()

    update_fields_for_notification = ['status']
    if previously_approved_items_exist and items_to_delete_if_modification_rejected.exists():
        items_to_delete_if_modification_rejected.delete()
        order.status = Order.STATUS_APPROVED
        if not order.taken_by_staff:
            order.taken_by_staff = user
            update_fields_for_notification.append('taken_by_staff')
        if not order.approved_at:
            order.approved_at = timezone.now()
            update_fields_for_notification.append('approved_at')
        order.save(update_fields=update_fields_for_notification)
    else:
        order.status = Order.STATUS_REJECTED
        order.taken_by_staff = user
        update_fields_for_notification.append('taken_by_staff')
        order.save(update_fields=update_fields_for_notification)

    order.refresh_from_db()

    # <<< YENİ: Bildirimi doğrudan ve sadece buradan gönderiyoruz >>>
    transaction.on_commit(
        lambda: send_order_update_notification(
            order=order,  # order_id yerine order nesnesi
            created=False, 
            update_fields=update_fields_for_notification
        )
    )
    # <<< GÜNCELLEME SONU >>>
    
    order_serializer = OrderSerializer(order, context={'request': request})
    
    return Response(order_serializer.data, status=status.HTTP_200_OK)


@transaction.atomic
def mark_order_picked_up_by_waiter_action(view_instance, request, pk=None):
    """Siparişi garson tarafından mutfaktan alınmış olarak işaretler."""
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
    
    # <<< YENİ: Bildirimi doğrudan ve sadece buradan gönderiyoruz >>>
    transaction.on_commit(
        lambda: send_order_update_notification(
            order=order,  # order_id yerine order nesnesi
            created=False, 
            update_fields=['status']
        )
    )
    # <<< GÜNCELLEME SONU >>>

    order_serializer = OrderSerializer(order, context={'request': request})
    return Response(order_serializer.data, status=status.HTTP_200_OK)


@transaction.atomic
def deliver_all_items_action(view_instance, request, pk=None):
    """Siparişin tüm kalemlerini müşteriye teslim edilmiş olarak işaretler."""
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

    # <<< YENİ: Bildirimi doğrudan ve sadece buradan gönderiyoruz >>>
    transaction.on_commit(
        lambda: send_order_update_notification(
            order=order,  # order_id yerine order nesnesi
            created=False, 
            update_fields=['delivered_at']  # ya da daha genel bir tip
        )
    )
    # <<< GÜNCELLEME SONU >>>

    order_serializer = OrderSerializer(order, context={'request': request})
    return Response(order_serializer.data, status=status.HTTP_200_OK)