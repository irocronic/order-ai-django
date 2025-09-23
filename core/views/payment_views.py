# core/views/payment_views.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import transaction

from ..models import Payment, Business, Order
from ..serializers import PaymentSerializer
from .order_views import get_user_business
# YENİ EKLENEN IMPORT'LAR
from ..tasks import send_socket_io_notification 
import logging

logger = logging.getLogger(__name__)

class PaymentViewSet(viewsets.ModelViewSet):
    """
    Ödeme işlemlerini doğrudan yönetir.
    Genellikle sipariş üzerinden ödeme alınır (OrderViewSet.mark_as_paid),
    ancak bu ViewSet doğrudan Payment objeleri üzerinde işlem yapmak için de kullanılabilir.
    """
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user) # Helper fonksiyonu kullan

        if not user_business:
            return Payment.objects.none()
        
        return Payment.objects.filter(order__business=user_business).select_related('order__business')

    def perform_create(self, serializer):
        user = self.request.user
        order_instance = serializer.validated_data.get('order')
        
        if not order_instance:
            raise PermissionDenied("Ödeme için bir sipariş belirtilmelidir.")

        user_business = get_user_business(user) # Helper fonksiyonu kullan
        
        if not user_business:
            raise PermissionDenied("Ödeme oluşturmak için yetkili bir işletmeniz bulunmuyor.")

        if order_instance.business != user_business:
            if not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Bu sipariş sizin işletmenize ait değil, ödeme alamazsınız.")
        
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        payment_instance = serializer.instance
        user_business = get_user_business(user)

        if not user_business or payment_instance.order.business != user_business:
            if not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Bu ödemeyi güncelleme yetkiniz yok.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business or instance.order.business != user_business:
             if not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Bu ödemeyi silme yetkiniz yok.")
        instance.delete()

# +++++++++++++++++++++ YENİ EKLENEN BÖLÜM +++++++++++++++++++++
@api_view(['POST'])
@permission_classes([AllowAny]) # Bu endpoint'e dış servislerden (ödeme sağlayıcı) istek geleceği için kimlik doğrulaması gerektirmez.
@transaction.atomic
def payment_provider_webhook(request):
    """
    Ödeme sağlayıcısından (örn: Stripe, Adyen) gelen anlık durum güncellemelerini işler.
    Bu, fiziksel POS cihazındaki işlemin sonucunu backend'e bildirir.
    """
    payload = request.data
    event_type = payload.get('type') # Bu, sağlayıcının dokümantasyonuna göre değişir.

    logger.info(f"Payment Webhook alındı: Event Tipi -> {event_type}")

    # Örnek olarak 'terminal.payment.succeeded' event'ini işleyelim.
    if event_type == 'terminal.payment.succeeded':
        try:
            payment_intent = payload['data']['object']
            metadata = payment_intent.get('metadata', {})
            order_id = metadata.get('order_id')
            terminal_id = metadata.get('terminal_id')

            if not order_id:
                logger.error("Webhook hatası: Payload içinde 'order_id' bulunamadı.")
                return Response({'status': 'error', 'message': 'Missing order_id'}, status=status.HTTP_400_BAD_REQUEST)

            order = Order.objects.select_for_update().get(id=int(order_id))

            if order.is_paid:
                logger.warning(f"Webhook uyarısı: Sipariş #{order_id} zaten ödenmiş durumda.")
                return Response({'status': 'ok', 'message': 'Order already paid'}, status=status.HTTP_200_OK)

            # Siparişi ödenmiş olarak işaretle ve tamamla
            order.is_paid = True
            order.status = Order.STATUS_COMPLETED
            order.save(update_fields=['is_paid', 'status'])
            
            # Ödeme kaydını oluştur
            Payment.objects.create(
                order=order,
                payment_type='credit_card', # POS cihazı olduğu için
                amount=Decimal(payment_intent['amount']) / 100 # Tutar genellikle 'cent' olarak gelir.
            )
            
            logger.info(f"Sipariş #{order_id} POS cihazı ({terminal_id}) üzerinden başarıyla ödendi.")

            # Flutter uygulamasına Socket.IO ile bildirim gönder
            room = f"business_{order.business_id}"
            event = 'pos_payment_update'
            data = {'status': 'success', 'order_id': order.id}
            send_socket_io_notification(room, event, data)
            logger.info(f"Flutter uygulamasına '{event}' olayı gönderildi. Oda: {room}")

        except Order.DoesNotExist:
            logger.error(f"Webhook hatası: Sipariş ID '{order_id}' bulunamadı.")
            return Response({'status': 'error', 'message': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Webhook işlenirken kritik hata: {e}", exc_info=True)
            return Response({'status': 'error', 'message': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif event_type == 'terminal.payment.failed':
         # Başarısız ödeme durumunu işle
        payment_intent = payload['data']['object']
        metadata = payment_intent.get('metadata', {})
        order_id = metadata.get('order_id')
        
        if order_id:
            try:
                order = Order.objects.get(id=int(order_id))
                room = f"business_{order.business_id}"
                event = 'pos_payment_update'
                data = {'status': 'failed', 'order_id': order.id, 'error': 'POS cihazında ödeme başarısız oldu.'}
                send_socket_io_notification(room, event, data)
                logger.warning(f"Sipariş #{order_id} için POS ödemesi başarısız oldu. Flutter'a bildirim gönderildi.")
            except Order.DoesNotExist:
                 logger.error(f"Webhook (failed event) hatası: Sipariş ID '{order_id}' bulunamadı.")

    # Sağlayıcıya isteğin başarıyla alındığını bildir





def payment_provider_webhook(request):
    # ... (imza doğrulama ve event ayrıştırma kodları)
    
    # ### DEMO İÇİN MEVCUT YAPI KORUNUYOR ###
    payload = request.data
    event_type = payload.get('type')
    
    if event_type == 'terminal.payment.succeeded':
        # ... (mevcut başarılı ödeme kodu)
        pass
    
    elif event_type == 'terminal.payment.failed':
        # ... (mevcut başarısız ödeme kodu)
        pass
        
    # +++ YENİ BÖLÜM BAŞLANGICI +++
    elif event_type == 'terminal.payment.canceled':
        payment_intent = payload['data']['object']
        metadata = payment_intent.get('metadata', {})
        order_id = metadata.get('order_id')
        
        if order_id:
            try:
                order = Order.objects.get(id=int(order_id))
                room = f"business_{order.business_id}"
                event = 'pos_payment_update'
                data = {'status': 'canceled', 'order_id': order.id, 'error': 'Ödeme terminalden iptal edildi.'}
                send_socket_io_notification(room, event, data)
                logger.warning(f"Sipariş #{order_id} için POS ödemesi iptal edildi. Flutter'a bildirim gönderildi.")
            except Order.DoesNotExist:
                 logger.error(f"Webhook (canceled event) hatası: Sipariş ID '{order_id}' bulunamadı.")
    # +++ YENİ BÖLÜM SONU +++


    return Response({'status': 'received'}, status=status.HTTP_200_OK)

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++