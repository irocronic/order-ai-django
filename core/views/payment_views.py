# core/views/payment_views.py (GÜNCELLENMİŞ VE TAM SÜRÜM)

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import transaction
from django.http import HttpResponse
from django.conf import settings
from decimal import Decimal
import logging
import stripe

from ..models import Payment, Business, Order
from ..serializers import PaymentSerializer
from ..utils.order_helpers import get_user_business
from ..tasks import send_socket_io_notification
from ..services import payment_terminal_service # Yeni, modüler servis yapısını import et

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


@api_view(['POST'])
@permission_classes([AllowAny])
@transaction.atomic
def payment_provider_webhook(request):
    """
    Aktif ödeme sağlayıcısından gelen webhook'ları işler.
    Tüm mantık, seçilen servis sınıfı tarafından yönetilir.
    """
    try:
        # Fabrika, ayardaki aktif sağlayıcıyı seçip ilgili handle_webhook metodunu çağıracak
        order, payment = payment_terminal_service.handle_webhook(request)

        if order and payment:
            # Ödeme başarılıysa siparişi güncelle ve Flutter'a bildirim gönder
            order.is_paid = True
            order.status = Order.STATUS_COMPLETED
            order.save(update_fields=['is_paid', 'status'])
            logger.info(f"Sipariş #{order.id} POS webhook üzerinden başarıyla ödendi.")

            room = f"business_{order.business_id}"
            event_name = 'pos_payment_update'
            data = {'status': 'success', 'order_id': order.id}
            send_socket_io_notification(room, event_name, data)
            logger.info(f"Flutter'a '{event_name}' olayı gönderildi. Oda: {room}")
        
        return HttpResponse(status=200)

    except PermissionError as e:
        logger.warning(f"[Webhook] Yetki hatası: {e}")
        return HttpResponse(status=403)
    except (ValueError, Order.DoesNotExist) as e:
        logger.error(f"[Webhook] Geçersiz veri veya bulunamayan sipariş: {e}")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"[Webhook] İşlenirken kritik hata: {e}", exc_info=True)
        return HttpResponse(status=500)