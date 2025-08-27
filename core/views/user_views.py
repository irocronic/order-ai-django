# core/views/user_views.py

from rest_framework import generics, viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

# --- GÜNCELLENEN IMPORTLAR BAŞLANGICI ---
from ..mixins import LimitCheckMixin
from subscriptions.models import Subscription, Plan
# Django'nun zaman ve zaman dilimi araçları
from django.utils import timezone
from datetime import timedelta, datetime # datetime eklendi
import pytz
# Gerekli modeller
from ..models import Business, NOTIFICATION_EVENT_TYPES, KDSScreen, ScheduledShift
# --- GÜNCELLENEN IMPORTLAR SONU ---

from ..serializers import (
    AccountSettingsSerializer,
    StaffUserSerializer,
    StaffPermissionUpdateSerializer,
    StaffNotificationPermissionUpdateSerializer
)
from ..permissions import IsBusinessOwnerAndOwnerOfStaff
from ..utils.order_helpers import get_user_business, PermissionKeys

User = get_user_model()

# AccountSettingsView sınıfı aynı kalıyor...
class AccountSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = AccountSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class StaffUserViewSet(LimitCheckMixin, viewsets.ModelViewSet):
    """
    İşletme sahiplerinin kendi personellerini (staff ve kitchen_staff) yönetmesi için API endpoint'leri.
    Yeni personel oluştururken abonelik limitlerini kontrol eder.
    """
    serializer_class = StaffUserSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwnerAndOwnerOfStaff]

    # Mixin için gerekli alanlar
    limit_resource_name = "Personel"
    limit_field_name = "max_staff"

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)
        
        if user_business:
            return User.objects.filter(
                associated_business=user_business,
                user_type__in=['staff', 'kitchen_staff']
            ).prefetch_related('accessible_kds_screens')
        return User.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business:
            raise PermissionDenied("Personel eklemek için yetkili bir işletmeniz bulunmuyor.")
        
        # Limit kontrolü
        try:
            subscription = user_business.subscription
            if not subscription.plan:
                raise ValidationError({'detail': 'İşletme için aktif bir abonelik planı bulunamadı.', 'code': 'subscription_error'})
            
            limit = getattr(subscription.plan, self.limit_field_name)
            current_count = self.get_queryset().count()

            if current_count >= limit:
                raise ValidationError({
                    'detail': f"{self.limit_resource_name} oluşturma limitinize ({limit}) ulaştınız. Lütfen paketinizi yükseltin.",
                    'code': 'limit_reached'
                })
        except (Subscription.DoesNotExist, AttributeError):
            raise ValidationError({'detail': 'Abonelik planı bulunamadı veya limitler tanımlanmamış.', 'code': 'subscription_error'})
        
        staff_user_type = serializer.validated_data.get('user_type', self.request.data.get('user_type', 'staff'))
        if staff_user_type not in ['staff', 'kitchen_staff']:
            raise ValidationError({"user_type": "Geçerli bir personel tipi ('staff' veya 'kitchen_staff') seçilmelidir."})

        assigned_kds_screens = serializer.validated_data.get('accessible_kds_screens', [])
        for kds_screen in assigned_kds_screens:
            if kds_screen.business != user_business:
                raise PermissionDenied(
                    f"Atanmak istenen KDS ekranı ('{kds_screen.name}') bu işletmeye ait değil."
                )
        
        serializer.save(
            associated_business=user_business,
            user_type=staff_user_type,
            is_active=serializer.validated_data.get('is_active', True),
            is_approved_by_admin=True
        )

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        user_business = get_user_business(user)

        if not user_business or instance.associated_business != user_business:
            raise PermissionDenied("Bu personeli güncelleme yetkiniz yok.")

        if 'accessible_kds_screens' in serializer.validated_data:
            assigned_kds_screens = serializer.validated_data.get('accessible_kds_screens', [])
            for kds_screen in assigned_kds_screens:
                if kds_screen.business != user_business:
                    raise PermissionDenied(
                        f"Atanmak istenen KDS ekranı ('{kds_screen.name}') personelin işletmesine ait değil."
                    )
        
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()

    @action(detail=True, methods=['put', 'patch'], serializer_class=StaffPermissionUpdateSerializer, url_path='permissions')
    def update_permissions(self, request, pk=None):
        staff_user = self.get_object()
        if staff_user.user_type not in ['staff', 'kitchen_staff']:
            return Response(
                {"detail": "Sadece personel veya mutfak personeli kullanıcıların ekran izinleri düzenlenebilir."},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(staff_user, data=request.data, partial=request.method == 'PATCH')
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(StaffUserSerializer(staff_user, context={'request': request}).data)

    @action(detail=True, methods=['put', 'patch'], serializer_class=StaffNotificationPermissionUpdateSerializer, url_path='notification-kds-permissions')
    def update_notification_and_kds_permissions(self, request, pk=None):
        staff_user = self.get_object()
        
        if staff_user.user_type not in ['staff', 'kitchen_staff']:
            return Response(
                {"detail": "Sadece personel veya mutfak personeli kullanıcıların izinleri bu arayüzden düzenlenebilir."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(staff_user, data=request.data, partial=request.method == 'PATCH')
        serializer.is_valid(raise_exception=True)

        if 'accessible_kds_screen_ids' in request.data:
            assigned_kds_screens_instances = serializer.validated_data.get('accessible_kds_screens', [])
            user_business = staff_user.associated_business
            for kds_screen in assigned_kds_screens_instances:
                if kds_screen.business != user_business:
                    raise PermissionDenied(
                        f"Atanmak istenen KDS ekranı ('{kds_screen.name}') personelin işletmesine ait değil."
                    )
        
        serializer.save()
        return Response(StaffUserSerializer(staff_user, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='has-shifts')
    def has_shifts(self, request, pk=None):
        staff_id = pk
        user = request.user
        business = get_user_business(user)
        
        staff_member = self.get_object() 
        
        if staff_member.id != int(staff_id):
            raise PermissionDenied("Yetkisiz işlem.")

        if staff_member.associated_business != business:
            raise PermissionDenied("Bu personelin bilgilerini görme yetkiniz yok.")

        has_shifts_assigned = ScheduledShift.objects.filter(staff_id=staff_id).exists()
        
        return Response({
            'staff_id': staff_id,
            'has_shifts': has_shifts_assigned
        })

    # +++++++++++++++++++++ GÜNCELLENMİŞ/EKLENMİŞ BÖLÜM BAŞLANGICI +++++++++++++++++++++
    @action(detail=False, methods=['get'], url_path='current-shift')
    def get_current_shift(self, request):
        """
        Giriş yapmış olan personel (staff/kitchen_staff) kullanıcısının
        o anki aktif vardiyasını ve UTC formatında bitiş zamanını döndürür.
        """
        user = request.user
        if user.user_type not in ['staff', 'kitchen_staff']:
            return Response(
                {"detail": "Bu endpoint sadece personel kullanıcıları içindir."},
                status=status.HTTP_403_FORBIDDEN
            )

        business = user.associated_business
        if not business:
            return Response(
                {"detail": "Kullanıcı bir işletmeye atanmamış."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            business_tz = pytz.timezone(business.timezone)
        except pytz.UnknownTimeZoneError:
            business_tz = timezone.get_current_timezone()
        
        now_in_business_tz = timezone.now().astimezone(business_tz)
        today = now_in_business_tz.date()
        yesterday = today - timedelta(days=1)
        current_time = now_in_business_tz.time()

        potential_shifts = ScheduledShift.objects.filter(
            staff=user,
            date__in=[today, yesterday]
        ).select_related('shift')

        active_shift = None
        for scheduled_shift in potential_shifts:
            shift = scheduled_shift.shift
            shift_start_time = shift.start_time
            shift_end_time = shift.end_time

            # Normal (aynı gün biten) vardiya
            if shift_start_time <= shift_end_time:
                if scheduled_shift.date == today and shift_start_time <= current_time <= shift_end_time:
                    active_shift = scheduled_shift
                    break
            # Gece yarısını geçen vardiya
            else:
                if (scheduled_shift.date == today and current_time >= shift_start_time) or \
                   (scheduled_shift.date == yesterday and current_time <= shift_end_time):
                    active_shift = scheduled_shift
                    break
        
        if active_shift:
            # Vardiyanın bitiş zamanını tam bir DateTime nesnesine çevirelim
            shift_end_date = active_shift.date
            if active_shift.shift.start_time > active_shift.shift.end_time: # Gece vardiyası ise
                shift_end_date += timedelta(days=1)

            end_datetime_naive = datetime.combine(shift_end_date, active_shift.shift.end_time)
            end_datetime_aware = business_tz.localize(end_datetime_naive)

            return Response({
                "id": active_shift.id,
                "shift_id": active_shift.shift.id,
                "shift_name": active_shift.shift.name,
                "start_time": active_shift.shift.start_time.strftime('%H:%M'),
                "end_time": active_shift.shift.end_time.strftime('%H:%M'),
                "date": active_shift.date.strftime('%Y-%m-%d'),
                "end_datetime_utc": end_datetime_aware.isoformat() # Flutter'ın kolayca parse etmesi için ISO formatı
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {"detail": "Şu an için aktif bir vardiya bulunamadı."},
                status=status.HTTP_404_NOT_FOUND
            )
    # +++++++++++++++++++++ GÜNCELLENMİŞ/EKLENMİŞ BÖLÜM SONU +++++++++++++++++++++