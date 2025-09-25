# core/views/order_actions/item_actions.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging
from asgiref.sync import async_to_sync

from makarna_project.asgi import sio
from ...models import Order, MenuItem, MenuItemVariant, OrderItem, OrderItemExtra, NOTIFICATION_EVENT_TYPES
from ...serializers import OrderSerializer
from ...utils.order_helpers import PermissionKeys
# === DEĞİŞİKLİK: Artık sinyal fonksiyonunu kullanmayacağız ===
# from ...signals.order_signals import send_order_update_notification
from ...utils.json_helpers import convert_decimals_to_strings

logger = logging.getLogger(__name__)


@transaction.atomic
def add_item_action(view_instance, request, pk=None):
    """
    Mevcut bir siparişe yeni bir ürün kalemi ekler veya mevcut kalemin miktarını artırır.
    Bildirim, merkezi sinyal yerine doğrudan buradan gönderilir.
    """
    order = view_instance.get_object()
    user = request.user

    if not (order.status == Order.STATUS_PENDING_APPROVAL and order.customer is None and order.taken_by_staff is None):
        view_instance._check_order_modifiable(order, action_name="Ürün ekleme")

    if not (user.user_type == 'business_owner' or
            (user.user_type == 'staff' and PermissionKeys.TAKE_ORDERS in user.staff_permissions)):
        raise PermissionDenied("Bu siparişe ürün ekleme yetkiniz yok.")

    menu_item_id = request.data.get('menu_item_id')
    variant_id = request.data.get('variant_id')
    quantity_to_add = int(request.data.get('quantity', 1))
    table_user_name = request.data.get('table_user')
    extras_data_raw = request.data.get('extras', [])

    if not menu_item_id:
        return Response({'detail': 'menu_item_id gereklidir.'}, status=status.HTTP_400_BAD_REQUEST)
    if quantity_to_add <= 0:
        return Response({'detail': 'Miktar pozitif bir sayı olmalıdır.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        menu_item = MenuItem.objects.get(id=int(menu_item_id), business=order.business)
    except (ValueError, MenuItem.DoesNotExist):
        return Response({'detail': 'Menü öğesi bulunamadı veya bu işletmeye ait değil.'}, status=status.HTTP_400_BAD_REQUEST)

    variant_instance = None
    if variant_id is not None:
        try:
            variant_instance = MenuItemVariant.objects.get(id=int(variant_id), menu_item=menu_item)
            if variant_instance.is_extra:
                return Response({'detail': 'Seçilen varyant bir ana ürün varyantı olmalı, ekstra değil.'}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, MenuItemVariant.DoesNotExist):
            return Response({'detail': 'Varyant bulunamadı.'}, status=status.HTTP_404_NOT_FOUND)
    elif menu_item.variants.filter(is_extra=False).exists():
        return Response({'detail': f"'{menu_item.name}' ürünü için lütfen bir seçenek (varyant) belirtin."}, status=status.HTTP_400_BAD_REQUEST)

    valid_extras_for_item = []
    if isinstance(extras_data_raw, list):
        for extra_data in extras_data_raw:
            extra_variant_id = extra_data.get('variant')
            extra_quantity = extra_data.get('quantity', 1)
            try:
                extra_variant = MenuItemVariant.objects.get(id=extra_variant_id, menu_item=menu_item, is_extra=True)
                valid_extras_for_item.append({'variant': extra_variant, 'quantity': extra_quantity})
            except MenuItemVariant.DoesNotExist:
                logger.warning(f"Sipariş #{order.id} için geçersiz ekstra ID'si ({extra_variant_id}) gönderildi.")

    item_data = {
        'menu_item': menu_item,
        'variant': variant_instance,
        'quantity': quantity_to_add,
        'table_user': table_user_name,
        'valid_extras': valid_extras_for_item,
    }
    
    is_awaiting_staff_approval_flag = order.status == Order.STATUS_PENDING_APPROVAL

    processed_item = view_instance._add_or_update_order_item_internal(
        order,
        item_data,
        is_awaiting_staff_approval_flag=is_awaiting_staff_approval_flag
    )
    if not processed_item:
        return Response({'detail': 'Sipariş kalemi işlenirken bir hata oluştu.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Sipariş durumu güncelleniyor
    update_fields = []
    if order.status != Order.STATUS_APPROVED:
        order.status = Order.STATUS_APPROVED
        update_fields.append('status')
    if not order.taken_by_staff:
        order.taken_by_staff = user
        update_fields.append('taken_by_staff')
    if not order.approved_at:
        order.approved_at = timezone.now()
        update_fields.append('approved_at')

    if update_fields:
        order.save(update_fields=update_fields)

    order.refresh_from_db()
    order_serializer = OrderSerializer(order, context={'request': request})
    
    # === GÜNCELLEME: Sinyal yerine doğrudan Socket.IO event'i gönderiliyor ===
    def send_socket_notification():
        if sio:
            room_name = f'business_{order.business.id}'
            payload = {
                'event_type': 'order_item_added',
                'message_key': 'notificationOrderItemAdded',
                'message_args': {
                    'orderId': str(order.id),
                    'productName': menu_item.name,
                    'quantity': str(quantity_to_add)
                },
                'updated_order_data': convert_decimals_to_strings(order_serializer.data),
            }
            try:
                async_to_sync(sio.emit)('order_status_update', payload, room=room_name)
                logger.info(f"Socket.IO 'order_item_added' event for Order ID {order.id} sent.")
            except Exception as e:
                logger.error(f"Socket.IO emit error in add_item_action: {e}")

    transaction.on_commit(send_socket_notification)
    
    return Response(order_serializer.data, status=status.HTTP_200_OK)


@transaction.atomic
def deliver_item_action(view_instance, request, pk=None):
    """Tek bir sipariş kalemini müşteriye teslim edildi olarak işaretler."""
    order = view_instance.get_object()
    if order.is_paid or order.status == Order.STATUS_COMPLETED:
        raise PermissionDenied("Ödenmiş veya tamamlanmış siparişin kalemleri değiştirilemez.")

    view_instance._check_order_modifiable(order, action_name="Ürün teslim etme")
    user = request.user

    if not (user.user_type == 'business_owner' or
            (user.user_type == 'staff' and PermissionKeys.TAKE_ORDERS in user.staff_permissions)):
        raise PermissionDenied("Sipariş kalemi teslim etme yetkiniz yok.")

    order_item_id_val = request.data.get('order_item_id')
    if not order_item_id_val:
        return Response({'detail': "'order_item_id' alanı zorunludur."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order_item_id = int(order_item_id_val)
        order_item = order.order_items.get(id=order_item_id)
    except (ValueError, TypeError):
        return Response({'detail': 'Geçersiz order_item_id formatı.'}, status=status.HTTP_400_BAD_REQUEST)
    except OrderItem.DoesNotExist:
        return Response({'detail': 'Sipariş kalemi bulunamadı.'}, status=status.HTTP_404_NOT_FOUND)

    if order_item.delivered:
        logger.info(f"[DELIVER_ITEM] OrderItem ID {order_item_id} is already delivered.")
        return Response(OrderSerializer(order, context={'request': request}).data, status=status.HTTP_200_OK)

    order_item.delivered = True
    order_item.save(update_fields=['delivered'])
    logger.info(f"[DELIVER_ITEM] OrderItem ID {order_item_id} marked as delivered successfully for Order ID {order.id}.")

    all_items_delivered = not order.order_items.filter(delivered=False).exists()
    order_updated = False
    if all_items_delivered and order.delivered_at is None:
        order.delivered_at = timezone.now()
        order.save(update_fields=['delivered_at'])
        order_updated = True
        logger.info(f"[DELIVER_ITEM] All items in Order ID {order.id} are now delivered. Order delivered_at updated.")

    order.refresh_from_db()
    order_serializer = OrderSerializer(order, context={'request': request})

    if sio:
        room_name = f'business_{order.business.id}'
        payload = {
            'event_type': 'order_item_delivered',
            'message': f"Sipariş #{order.id}, kalem #{order_item.id} ({order_item.menu_item.name}) teslim edildi.",
            'order_id': order.id,
            'item_id': order_item.id,
            'all_items_delivered_in_order': all_items_delivered and order_updated,
            'updated_order_data': convert_decimals_to_strings(order_serializer.data)
        }
        try:
            async_to_sync(sio.emit)('order_status_update', payload, room=room_name)
            logger.info(f"Socket.IO 'order_status_update' (item_delivered) for Order ID {order.id}, Item {order_item.id} sent.")
        except Exception as e_socket:
            logger.error(f"Socket.IO error sending order_item_delivered event: {e_socket}", exc_info=True)


    return Response(order_serializer.data, status=status.HTTP_200_OK)