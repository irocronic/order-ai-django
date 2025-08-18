# core/views/user_views.py

from rest_framework import generics, viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

# --- GÜNCELLENEN IMPORTLAR ---
from ..mixins import LimitCheckMixin
from subscriptions.models import Subscription, Plan
# --- /GÜNCELLENEN IMPORTLAR ---

from ..models import Business, NOTIFICATION_EVENT_TYPES, KDSScreen, ScheduledShift
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

    # --- GÜNCELLENMİŞ perform_create METODU ---
    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business:
            raise PermissionDenied("Personel eklemek için yetkili bir işletmeniz bulunmuyor.")
        
        # Limit kontrolü
        try:
            subscription = user_business.subscription
            # Limitin, aboneliğe bağlı Plan'dan geldiğini kontrol et
            if not subscription.plan:
                raise ValidationError({'detail': 'İşletme için aktif bir abonelik planı bulunamadı.', 'code': 'subscription_error'})
            
            # Limiti subscription.plan üzerinden al
            limit = getattr(subscription.plan, self.limit_field_name)
            current_count = self.get_queryset().count()

            if current_count >= limit:
                raise ValidationError({
                    'detail': f"{self.limit_resource_name} oluşturma limitinize ({limit}) ulaştınız. Lütfen paketinizi yükseltin.",
                    'code': 'limit_reached'
                })
        except (Subscription.DoesNotExist, AttributeError):
            raise ValidationError({'detail': 'Abonelik planı bulunamadı veya limitler tanımlanmamış.', 'code': 'subscription_error'})
        
        # Kalan mantık aynı
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
    # --- /GÜNCELLENMİŞ perform_create METODU ---

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