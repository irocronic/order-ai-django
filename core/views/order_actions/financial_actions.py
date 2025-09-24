# core/views/order_actions/financial_actions.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.db import transaction
from django.db.models import Prefetch, Q
from decimal import Decimal
import logging
import uuid
from asgiref.sync import async_to_sync

from makarna_project.asgi import sio
from ...models import Order, CreditPaymentDetails, Payment
from ...serializers import OrderSerializer
from ...utils.order_helpers import PermissionKeys, get_user_business
from ...utils.json_helpers import convert_decimals_to_strings
from ...services.payment_service_factory import PaymentServiceFactory

logger = logging.getLogger(__name__)

@transaction.atomic
def _finalize_order_as_paid(order: Order, payment_type: str, amount: Decimal, request_user):
    """Bir siparişi ödenmiş olarak işaretler ve ilgili işlemleri yapar."""
    if order.is_paid:
        # Zaten ödenmişse tekrar işlem yapma
        return order

    if hasattr(order, 'credit_payment_details') and order.credit_payment_details:
        credit_details = order.credit_payment_details
        if credit_details.paid_at is None:
            credit_details.paid_at = timezone.now()
            credit_details.save(update_fields=['paid_at'])
            logger.info(f"Sipariş #{order.id} için veresiye kaydı kapatıldı.")

    order.is_paid = True
    order.status = Order.STATUS_COMPLETED
    if order.delivered_at is None:
        order.delivered_at = timezone.now()
        order.order_items.filter(delivered=False).update(delivered=True)
    
    order.save(update_fields=['is_paid', 'status', 'delivered_at'])
    logger.info(f"Order ID {order.id} is_paid=True, status={Order.STATUS_COMPLETED} olarak güncellendi.")

    payment_instance, created = Payment.objects.update_or_create(
        order=order,
        defaults={'payment_type': payment_type, 'amount': amount}
    )
    logger.info(f"Payment ID {payment_instance.id} (created: {created}) kaydedildi. Stok düşürme sinyali tetiklenecek.")
    
    return order

@transaction.atomic
def mark_as_paid_action(view_instance, request, pk=None):
    """Bir siparişi ödenmiş olarak işaretler ve ödeme kaydı oluşturur."""
    order = view_instance.get_object()
    user = request.user

    if order.status == Order.STATUS_PENDING_APPROVAL:
        raise PermissionDenied("Bu sipariş henüz onaylanmadı, ödeme alınamaz.")
    if order.status == Order.STATUS_REJECTED or order.status == Order.STATUS_CANCELLED:
        raise PermissionDenied("Reddedilmiş veya iptal edilmiş siparişler için ödeme alınamaz.")

    if not (user.user_type == 'business_owner' or
            (user.user_type == 'staff' and (PermissionKeys.TAKE_ORDERS in user.staff_permissions or PermissionKeys.MANAGE_CREDIT_SALES in user.staff_permissions))):
        raise PermissionDenied("Ödeme alma/işaretleme yetkiniz yok.")

    if order.is_paid:
        return Response({'detail': 'Bu sipariş zaten ödenmiş.'}, status=status.HTTP_400_BAD_REQUEST)

    payment_type = request.data.get('payment_type')
    amount_val = request.data.get('amount')

    if not payment_type:
        return Response({'detail': 'Ödeme türü belirtilmelidir.'}, status=status.HTTP_400_BAD_REQUEST)
    if amount_val is None:
        return Response({'detail': 'Ödeme tutarı belirtilmelidir.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = Decimal(str(amount_val))
        if amount <= 0:
            raise ValueError("Tutar pozitif bir sayı olmalıdır.")
    except (ValueError, TypeError):
        return Response({'detail': "Geçerli bir ödeme tutarı girin."}, status=status.HTTP_400_BAD_REQUEST)

    valid_payment_types = [choice[0] for choice in Payment.PAYMENT_CHOICES]
    if payment_type not in valid_payment_types:
        return Response({'detail': 'Geçersiz ödeme türü.'}, status=status.HTTP_400_BAD_REQUEST)

    order = _finalize_order_as_paid(order, payment_type, amount, request.user)
    
    original_table_id = order.table.id if order.table else None
    
    order.refresh_from_db()
    order_serializer = OrderSerializer(order, context={'request': request})
    
    if sio:
        room_name = f'business_{order.business.id}'
        payload = {
            'event_type': 'order_paid',
            'message': f"Sipariş #{order.id} ödendi.",
            'order_id': order.id,
            'table_id': original_table_id,
            'updated_order_data': order_serializer.data,
        }
        try:
            cleaned_payload = convert_decimals_to_strings(payload)
            async_to_sync(sio.emit)('order_status_update', cleaned_payload, room=room_name)
            logger.info(f"Socket.IO (Ödeme): 'order_status_update' (paid) {room_name} odasına gönderildi (Sipariş ID: {order.id}).")
        except Exception as e_socket:
            logger.error(f"Socket.IO event gönderilirken hata (ödeme - sipariş {order.id}): {e_socket}", exc_info=True)

    return Response(order_serializer.data, status=status.HTTP_200_OK)

def initiate_qr_payment_action(view_instance, request, pk=None):
    """QR ödeme isteği başlatma - MOCK TEST VERSIYONU"""
    try:
        order = view_instance.get_object()
        logger.info(f"Mock QR ödeme başlatılıyor: Order #{order.id}")
        
        # Mock QR data oluştur
        mock_qr_data = f"https://checkout.iyzipay.com/payment?token=mock_{order.id}_{uuid.uuid4().hex[:8]}"
        mock_transaction_id = str(uuid.uuid4())
        
        response_data = {
            'qr_data': mock_qr_data,
            'transaction_id': mock_transaction_id,
            'message': 'Mock QR ödeme oluşturuldu'
        }
        
        logger.info(f"Mock QR ödeme başarıyla oluşturuldu: {mock_transaction_id}")
        return Response(response_data, status=200)
        
    except Exception as e:
        logger.error(f"Mock QR ödeme hatası: {str(e)}", exc_info=True)
        return Response({
            'detail': f'Mock QR ödeme hatası: {str(e)}'
        }, status=400)

def check_qr_payment_status_action(view_instance, request, pk=None):
    """Başlatılmış bir QR ödemesinin durumunu kontrol eder - MOCK VERSIYONU."""
    order = view_instance.get_object()
    transaction_id = request.query_params.get('transaction_id')

    if not transaction_id:
        return Response({"detail": "transaction_id gereklidir."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Mock status response - %25 ihtimalle 'paid', geri kalanı 'pending'
        import random
        random.seed(hash(transaction_id) % (2**32))
        
        if random.random() < 0.25:  # %25 başarı oranı
            payment_status = "paid"
            # Mock ödeme başarılıysa, siparişi tamamla
            finalized_order = _finalize_order_as_paid(order, 'qr_code', order.grand_total, request.user)
            
            original_table_id = finalized_order.table.id if finalized_order.table else None
            finalized_order.refresh_from_db()
            order_serializer = OrderSerializer(finalized_order, context={'request': request})

            if sio:
                room_name = f'business_{finalized_order.business.id}'
                payload = {
                    'event_type': 'order_paid',
                    'message': f"Sipariş #{finalized_order.id} QR ile ödendi (Mock).",
                    'order_id': finalized_order.id,
                    'table_id': original_table_id,
                    'updated_order_data': order_serializer.data,
                }
                try:
                    cleaned_payload = convert_decimals_to_strings(payload)
                    async_to_sync(sio.emit)('order_status_update', cleaned_payload, room=room_name)
                    logger.info(f"Socket.IO (Mock QR Ödeme): 'order_status_update' (paid) {room_name} odasına gönderildi.")
                except Exception as e_socket:
                    logger.error(f"Socket.IO event gönderilirken hata (Mock QR ödeme): {e_socket}", exc_info=True)
        else:
            payment_status = "pending"
        
        status_response = {"status": payment_status}
        logger.debug(f"Mock QR durumu: {transaction_id} -> {payment_status}")
        
        return Response(status_response, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Mock QR ödeme durumu kontrol edilirken hata: {e}", exc_info=True)
        return Response({"detail": "Mock ödeme durumu kontrol edilirken bir hata oluştu."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@transaction.atomic
def save_credit_payment_action(view_instance, request, pk=None):
    """Bir siparişi veresiye olarak kaydeder."""
    order = view_instance.get_object()
    view_instance._check_order_modifiable(order, action_name="Veresiye kaydetme")
    user = request.user

    if not (user.user_type == 'business_owner' or
            (user.user_type == 'staff' and PermissionKeys.MANAGE_CREDIT_SALES in user.staff_permissions)):
        raise PermissionDenied("Veresiye kaydı oluşturma yetkiniz yok.")

    if order.is_paid:
        if hasattr(order, 'payment_info') and order.payment_info is not None:
            return Response({'detail': 'Bu sipariş zaten farklı bir yöntemle ödenmiş.'}, status=status.HTTP_400_BAD_REQUEST)

    customer_name = request.data.get('customer_name')
    customer_phone = request.data.get('customer_phone')
    notes = request.data.get('notes', '')

    if customer_name is not None:
        order.customer_name = customer_name
    if customer_phone is not None:
        order.customer_phone = customer_phone

    Payment.objects.filter(order=order).delete()

    CreditPaymentDetails.objects.update_or_create(
        order=order,
        defaults={'notes': notes, 'paid_at': None}
    )

    order.is_paid = False
    order.status = Order.STATUS_COMPLETED
    if order.delivered_at is None:
        order.delivered_at = timezone.now()
        order.order_items.filter(delivered=False).update(delivered=True)
    
    order.save(update_fields=['customer_name', 'customer_phone', 'is_paid', 'status', 'delivered_at'])
    logger.info(f"Order ID {order.id} veresiye olarak kaydedildi. is_paid={order.is_paid}, status={order.status}.")
    
    order.refresh_from_db()
    order_serializer = OrderSerializer(order, context={'request': request})
    
    if sio:
        room_name = f'business_{order.business.id}'
        payload = {
            'event_type': 'order_credit_sale',
            'message': f"Sipariş #{order.id} veresiyeye eklendi.",
            'order_id': order.id,
            'updated_order_data': order_serializer.data,
        }
        try:
            cleaned_payload = convert_decimals_to_strings(payload)
            async_to_sync(sio.emit)('order_status_update', cleaned_payload, room=room_name)
            logger.info(f"Socket.IO (Veresiye): 'order_status_update' (credit_sale) {room_name} odasına gönderildi (Sipariş ID: {order.id}).")
        except Exception as e_socket:
            logger.error(f"Socket.IO event gönderilirken hata (veresiye - sipariş {order.id}): {e_socket}", exc_info=True)

    return Response(order_serializer.data, status=status.HTTP_200_OK)

def list_credit_sales_action(view_instance, request):
    """Ödenmemiş veresiye satışları listeler."""
    user = request.user
    user_business = get_user_business(user)

    if user.user_type == 'staff' and PermissionKeys.MANAGE_CREDIT_SALES not in user.staff_permissions:
        raise PermissionDenied("Veresiye satışları görüntüleme yetkiniz yok.")

    base_queryset = view_instance.queryset

    if not user_business:
        if not (user.is_staff or user.is_superuser):
            raise PermissionDenied("Veresiye satışları görüntüleme yetkiniz yok.")
        queryset = base_queryset.filter(credit_payment_details__isnull=False, is_paid=False)
    else:
        queryset = base_queryset.filter(
            business=user_business,
            credit_payment_details__isnull=False,
            is_paid=False
        )
    
    page = view_instance.paginate_queryset(queryset)
    if page is not None:
        serializer = OrderSerializer(page, many=True, context={'request': request})
        return view_instance.get_paginated_response(serializer.data)

    serializer = OrderSerializer(queryset, many=True, context={'request': request})
    return Response(serializer.data)