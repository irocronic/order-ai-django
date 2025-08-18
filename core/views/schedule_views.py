# core/views/schedule_views.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action # @action için import eklendi
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, PermissionDenied
from datetime import datetime

# CustomUser importu artık burada gerekli değil, ancak başka yerlerde kullanılıyorsa kalabilir.
# Şimdilik temizlik açısından kaldırıyoruz, eğer başka bir yerde gerekirse tekrar eklenmelidir.
from ..models import Shift, ScheduledShift, CustomUser 
from ..serializers import ShiftSerializer, ScheduledShiftSerializer
from ..utils.order_helpers import get_user_business, PermissionKeys

class ShiftViewSet(viewsets.ModelViewSet):
    """Vardiya şablonlarını yönetmek için API (CRUD)."""
    serializer_class = ShiftSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        business = get_user_business(user)
        if business:
            return Shift.objects.filter(business=business)
        return Shift.objects.none()

    def perform_create(self, serializer):
        business = get_user_business(self.request.user)
        # Sadece işletme sahibi veya manage_staff izni olanlar şablon oluşturabilir.
        if not (self.request.user.user_type == 'business_owner' or
                (self.request.user.user_type == 'staff' and PermissionKeys.MANAGE_STAFF in self.request.user.staff_permissions)):
            raise PermissionDenied("Vardiya şablonu oluşturma yetkiniz yok.")
        serializer.save(business=business)


class ScheduledShiftViewSet(viewsets.ModelViewSet):
    """Personel vardiya atamalarını yönetmek için API (CRUD)."""
    serializer_class = ScheduledShiftSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        business = get_user_business(user)
        if not business:
            return ScheduledShift.objects.none()
        
        queryset = ScheduledShift.objects.filter(
            Q(staff__associated_business=business) | Q(shift__business=business)
        ).distinct().select_related('staff', 'shift')

        # Tarih aralığına göre filtreleme
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])
        
        return queryset

    @action(detail=False, methods=['post'], url_path='bulk_create')
    def bulk_create(self, request):
        """
        Birden çok personele, birden çok tarih için toplu şekilde vardiya atar.
        Payload: { "staff_ids": [1, 2], "dates": ["2025-06-20", "2025-06-21"], "shift_id": 3 }
        """
        user = request.user
        business = get_user_business(user)

        # Yetki kontrolü
        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STAFF in user.staff_permissions)):
            raise PermissionDenied("Toplu vardiya atama yetkiniz yok.")
        
        staff_ids = request.data.get('staff_ids')
        dates_str = request.data.get('dates')
        shift_id = request.data.get('shift_id')

        # Gerekli alanların validasyonu
        if not all([staff_ids, dates_str, shift_id]):
            raise ValidationError("staff_ids, dates ve shift_id alanları zorunludur.")
        if not isinstance(staff_ids, list) or not isinstance(dates_str, list):
            raise ValidationError("staff_ids ve dates list formatında olmalıdır.")
        
        # Shift ve Staff objelerini kontrol et
        shift = get_object_or_404(Shift, id=shift_id, business=business)
        staff_members = CustomUser.objects.filter(id__in=staff_ids, associated_business=business, user_type__in=['staff', 'kitchen_staff'])

        if len(staff_members) != len(staff_ids):
                raise ValidationError("Bazı personel ID'leri geçersiz veya bu işletmeye ait değil.")
        
        shifts_to_create = []
        for staff_id in staff_ids:
            for date_str in dates_str:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    shifts_to_create.append(
                        ScheduledShift(
                            staff_id=staff_id,
                            shift_id=shift_id,
                            date=date_obj
                        )
                    )
                except ValueError:
                    raise ValidationError(f"Geçersiz tarih formatı: {date_str}. YYYY-MM-DD formatını kullanın.")

        # Toplu kayıt işlemi. ignore_conflicts=True sayesinde,
        # eğer aynı gün aynı personele zaten bir vardiya atanmışsa hata vermez, onu atlar.
        # Bu, işlemi daha güvenli hale getirir.
        ScheduledShift.objects.bulk_create(shifts_to_create, ignore_conflicts=True)
        
        return Response(
            {"detail": f"{len(staff_ids)} personele {len(dates_str)} gün için vardiya başarıyla atandı."},
            status=status.HTTP_201_CREATED
        )