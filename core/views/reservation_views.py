# core/views/reservation_views.py

from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from ..models import Reservation, Business, Table # Table ve Business modelleri de import edildi
from ..serializers.reservation_serializers import ReservationSerializer, PublicReservationCreateSerializer
from ..utils.order_helpers import get_user_business
from ..tasks import send_order_update_task

# İşletme sahibi için
class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    # === HATA DÜZELTME: Temel queryset eklendi ===
    queryset = Reservation.objects.all()

    def get_queryset(self):
        # Temel queryset'i alıp üzerinde filtreleme yapıyoruz.
        queryset = super().get_queryset()
        user_business = get_user_business(self.request.user)
        if not user_business:
            return queryset.none()
        
        # Sadece gelecekteki ve bugünkü rezervasyonları getir
        return queryset.filter(
            business=user_business,
            reservation_time__gte=timezone.now().date()
        ).select_related('table')

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        reservation = self.get_object()
        reservation.status = Reservation.Status.CONFIRMED
        reservation.save(update_fields=['status'])
        # Opsiyonel: Müşteriye onay e-postası/SMS'i gönderilebilir.
        return Response(self.get_serializer(reservation).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reservation = self.get_object()
        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=['status'])
        return Response(self.get_serializer(reservation).data)

    @action(detail=True, methods=['post'])
    def mark_seated(self, request, pk=None):
        reservation = self.get_object()
        reservation.status = Reservation.Status.SEATED
        reservation.save(update_fields=['status'])
        return Response(self.get_serializer(reservation).data)

# Herkese açık web sitesi için
class PublicReservationCreateView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicReservationCreateSerializer

    def perform_create(self, serializer):
        business_slug = self.kwargs.get('business_slug')
        business = get_object_or_404(Business, slug=business_slug)
        
        if not hasattr(business, 'website') or not business.website.allow_reservations:
            raise serializers.ValidationError("Bu işletme şu anda online rezervasyon kabul etmemektedir.")
            
        reservation = serializer.save(business=business)
        
        # İşletme sahibine bildirim gönder
        message = (
            f"Yeni rezervasyon talebi: {reservation.customer_name} - "
            f"Masa {reservation.table.table_number} - "
            f"{reservation.reservation_time.strftime('%d.%m %H:%M')}"
        )
        
        extra_data = {
            'reservation_id': reservation.id,
            'is_reservation': True,
            'business_id': business.id # Bildirimin doğru işletmeye gitmesi için
        }
        
        # Celery task'ini tetikle
        send_order_update_task.delay(
            order_id=reservation.id, # Rezervasyon ID'sini order_id gibi kullanabiliriz
            event_type='reservation_pending_approval',
            message=message,
            extra_data=extra_data
        )