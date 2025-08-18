# core/views/order_actions/operational_actions.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
import logging
from asgiref.sync import async_to_sync

from makarna_project.asgi import sio
from ...models import Order, Table
from ...serializers import OrderSerializer
from ...utils.order_helpers import PermissionKeys, get_user_business
from ...signals.order_signals import send_order_update_notification

logger = logging.getLogger(__name__)


def transfer_order_action(view_instance, request):
    """Bir siparişi bir masadan diğerine transfer eder."""
    user = request.user
    user_business = get_user_business(user)

    if not user_business:
        return Response({"detail": "Bu işlem için yetkili bir işletmeniz bulunmuyor."}, status=status.HTTP_403_FORBIDDEN)

    if not (user.user_type == 'business_owner' or
            (user.user_type == 'staff' and PermissionKeys.TAKE_ORDERS in user.staff_permissions)):
        return Response({"detail": "Masa transferi yapma yetkiniz yok."}, status=status.HTTP_403_FORBIDDEN)

    order_id_val = request.data.get('order')
    new_table_id_val = request.data.get('new_table')

    if not order_id_val or not new_table_id_val:
        return Response({"detail": "Sipariş ID ve yeni masa ID'si gereklidir."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order_id = int(order_id_val)
        new_table_id = int(new_table_id_val)
    except ValueError:
        return Response({"detail": "Geçersiz ID formatı."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order_to_transfer = Order.objects.get(id=order_id, business=user_business)
        new_table = Table.objects.get(id=new_table_id, business=user_business)
    except Order.DoesNotExist:
        return Response({"detail": "Transfer edilecek sipariş bulunamadı veya işletmenize ait değil."}, status=status.HTTP_404_NOT_FOUND)
    except Table.DoesNotExist:
        return Response({"detail": "Yeni masa bulunamadı veya işletmenize ait değil."}, status=status.HTTP_404_NOT_FOUND)
    
    view_instance._check_order_modifiable(order_to_transfer, action_name="Masa transferi")

    if order_to_transfer.table == new_table:
        return Response({"detail": "Sipariş zaten bu masada."}, status=status.HTTP_400_BAD_REQUEST)
    
    if Order.objects.filter(
        table=new_table, is_paid=False, credit_payment_details__isnull=True, business=user_business
    ).exclude(id=order_to_transfer.id).exclude(
        Q(status=Order.STATUS_REJECTED) | Q(status=Order.STATUS_CANCELLED) | Q(status=Order.STATUS_COMPLETED)
    ).exists():
        return Response({"detail": f"Masa {new_table.table_number} başka bir aktif sipariş tarafından kullanılıyor."}, status=status.HTTP_400_BAD_REQUEST)

    original_table_number_for_notification = order_to_transfer.table.table_number if order_to_transfer.table else None

    order_to_transfer.table = new_table
    order_to_transfer.save(update_fields=['table'])

    logger.info(f"Sipariş {order_to_transfer.id}, Masa {original_table_number_for_notification or 'YOK'} -> Masa {new_table.table_number} olarak transfer edildi.")
    
    order_serializer = OrderSerializer(order_to_transfer, context={'request': request})

    transaction.on_commit(
        lambda: send_order_update_notification(
            order=order_to_transfer,
            created=False, 
            update_fields=['table']
        )
    )

    return Response(order_serializer.data, status=status.HTTP_200_OK)


def destroy_order_action(view_instance, instance: Order):
    """Bir siparişi iptal eder veya (admin ise) siler."""
    user = view_instance.request.user
    view_instance._check_order_modifiable(instance, action_name="Siparişi iptal etme/silme")

    if not (user.user_type == 'business_owner' or \
            (user.user_type == 'staff' and PermissionKeys.TAKE_ORDERS in user.staff_permissions) or \
            user.is_superuser):
        raise PermissionDenied("Bu siparişi iptal etme/silme yetkiniz yok.")

    order_id = instance.id
    
    if instance.status != Order.STATUS_CANCELLED and instance.status != Order.STATUS_COMPLETED :
        original_status_display = instance.get_status_display()
        instance.status = Order.STATUS_CANCELLED
        instance.save(update_fields=['status'])
        logger.info(f"Sipariş {order_id} (eski durum: {original_status_display}) kullanıcı {user.username} tarafından İPTAL EDİLDİ.")
        
        transaction.on_commit(
            lambda: send_order_update_notification(
                order=instance,
                created=False, 
                update_fields=['status']
            )
        )
        
        order_serializer_data = OrderSerializer(instance, context={'request': view_instance.request}).data
        return Response(order_serializer_data, status=status.HTTP_200_OK)
    
    elif user.is_superuser: 
        instance.delete()
        logger.info(f"Sipariş {order_id} SUPERUSER {user.username} tarafından VERİTABANINDAN SİLİNDİ.")
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    else:
        logger.info(f"Sipariş {order_id} zaten {instance.get_status_display()} durumunda, işlem yapılmadı.")
        return Response({"detail": f"Sipariş zaten {instance.get_status_display()} durumunda."}, status=status.HTTP_400_BAD_REQUEST)