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
import logging

logger = logging.getLogger(__name__)

# İşletme sahibi için
class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    queryset = Reservation.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        user_business = get_user_business(self.request.user)
        if not user_business:
            return queryset.none()
        return queryset.filter(
            business=user_business,
            reservation_time__gte=timezone.now().date()
        ).select_related('table')

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        reservation = self.get_object()
        reservation.status = Reservation.Status.CONFIRMED
        reservation.save(update_fields=['status'])
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

    def create(self, request, *args, **kwargs):
        business_slug = self.kwargs.get('business_slug')
        try:
            business = get_object_or_404(Business, slug=business_slug)

            if not hasattr(business, 'website') or not business.website.allow_reservations:
                return Response(
                    {"detail": "Bu işletme şu anda online rezervasyon kabul etmemektedir."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            reservation = serializer.save(business=business)

            # İşletme sahibine bildirim gönder
            try:
                message = (
                    f"Yeni rezervasyon talebi: {reservation.customer_name} - "
                    f"Masa {reservation.table.table_number} - "
                    f"{reservation.reservation_time.strftime('%d.%m %H:%M')}"
                )
                extra_data = {
                    'reservation_id': reservation.id,
                    'is_reservation': True,
                    'business_id': business.id
                }
                send_order_update_task.delay(
                    order_id=reservation.id,
                    event_type='reservation_pending_approval',
                    message=message,
                    extra_data=extra_data
                )
            except Exception as notify_err:
                logger.error(f"Rezervasyon bildirimi gönderilemedi: {notify_err}")

            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

        except Exception as exc:
            logger.error(f"Rezervasyon API Hatası: {exc}", exc_info=True)
            # Hatanın türüne göre status kodu ayarla
            error_code = getattr(exc, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)
            error_detail = str(exc)
            return Response(
                {
                    "error": "Rezervasyon oluşturulurken sunucu tarafında bir hata oluştu.",
                    "detail": error_detail,
                    "code": error_code
                },
                status=error_code
            )