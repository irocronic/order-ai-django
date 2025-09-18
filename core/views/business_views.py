# core/views/business_views.py

from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from ..mixins import LimitCheckMixin
from ..models import Business, Table, BusinessLayout
from ..serializers import BusinessSerializer, TableSerializer, BusinessLayoutSerializer
from ..utils.order_helpers import get_user_business, PermissionKeys


class BusinessViewSet(viewsets.ModelViewSet):
    """
    İşletme bilgilerini yönetir.
    İşletme sahibi kendi işletmesini, admin/staff tüm işletmeleri görebilir ve yönetebilir.
    """
    serializer_class = BusinessSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            if user.user_type == 'business_owner':
                try:
                    return Business.objects.filter(owner=user)
                except Business.DoesNotExist:
                    return Business.objects.none()
            elif user.is_staff or user.is_superuser:
                return Business.objects.all()
        return Business.objects.none()

    def perform_create(self, serializer):
        if self.request.user.user_type == 'business_owner':
            if hasattr(self.request.user, 'owned_business') and self.request.user.owned_business is not None:
                raise ValidationError({"detail": "Bu kullanıcıya ait zaten bir işletme mevcut."})
            serializer.save(owner=self.request.user, is_setup_complete=False)
        else:
            raise PermissionDenied({"detail": "Sadece işletme sahipleri yeni işletme oluşturabilir."})

    @action(detail=True, methods=['post'], url_path='complete-setup', permission_classes=[IsAuthenticated])
    def complete_setup(self, request, pk=None):
        business = self.get_object()
        if business.owner != request.user:
            return Response({"detail": "Bu işlem için yetkiniz yok. Sadece işletme sahibi bu işlemi yapabilir."}, status=status.HTTP_403_FORBIDDEN)
        if business.is_setup_complete:
            return Response({"detail": "İşletme kurulumu zaten tamamlanmış."}, status=status.HTTP_400_BAD_REQUEST)

        business.is_setup_complete = True
        business.save(update_fields=['is_setup_complete'])
        serializer = self.get_serializer(business)
        return Response({"detail": "İşletme kurulumu başarıyla tamamlandı.", "business": serializer.data}, status=status.HTTP_200_OK)

    def perform_update(self, serializer):
        business = self.get_object()
        if business.owner != self.request.user and not self.request.user.is_superuser:
            raise PermissionDenied({"detail": "Bu işletmeyi güncelleme yetkiniz yok."})
        serializer.save()

    def perform_destroy(self, instance):
        if instance.owner != self.request.user and not self.request.user.is_superuser:
            raise PermissionDenied({"detail": "Bu işletmeyi silme yetkiniz yok."})
        instance.delete()

class TableViewSet(LimitCheckMixin, viewsets.ModelViewSet):
    """
    Masaları yönetir. Giriş yapanın işletmesine ait tabloları döndürür.
    Yeni masa oluştururken abonelik limitlerini kontrol eder.
    """
    serializer_class = TableSerializer
    permission_classes = [IsAuthenticated]

    limit_resource_name = "Masa"
    limit_field_name = "max_tables"

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business:
            return Table.objects.none()

        if user.user_type == 'business_owner':
            return Table.objects.filter(business=user_business)
        
        elif user.user_type == 'staff':
            if PermissionKeys.TAKE_ORDERS in user.staff_permissions or \
               PermissionKeys.MANAGE_TABLES in user.staff_permissions:
                return Table.objects.filter(business=user_business)
            else:
                return Table.objects.none()
        
        return Table.objects.none()

    @action(detail=False, methods=['post'], url_path='bulk-update-positions')
    def bulk_update_positions(self, request, *args, **kwargs):
        """
        Birden çok masanın pozisyonunu tek bir istekte günceller.
        Request body: [{'id': 1, 'pos_x': 100.5, 'pos_y': 50.0, 'rotation': 90.0}, ...]
        """
        user_business = get_user_business(request.user)
        if not user_business:
            raise PermissionDenied("Bu işlem için yetkili bir işletmeniz bulunmuyor.")

        tables_data = request.data
        if not isinstance(tables_data, list):
            raise ValidationError({'detail': 'İstek gövdesi bir liste olmalıdır.'})

        table_ids = [item.get('id') for item in tables_data]
        tables_to_update = Table.objects.filter(id__in=table_ids, business=user_business)

        if len(table_ids) != tables_to_update.count():
            raise PermissionDenied("Bazı masalar bulunamadı veya işletmenize ait değil.")
            
        layout = user_business.layout

        with transaction.atomic():
            for data in tables_data:
                table = next((t for t in tables_to_update if t.id == data.get('id')), None)
                if table:
                    table.pos_x = data.get('pos_x')
                    table.pos_y = data.get('pos_y')
                    table.rotation = data.get('rotation', 0.0)
                    table.layout = layout
                    table.save(update_fields=['pos_x', 'pos_y', 'rotation', 'layout'])

        return Response({'status': 'success', 'message': f'{len(tables_data)} masanın pozisyonu güncellendi.'}, status=status.HTTP_200_OK)

class BusinessLayoutViewSet(viewsets.GenericViewSet, 
                              mixins.ListModelMixin,
                              mixins.RetrieveModelMixin, 
                              mixins.UpdateModelMixin):
    """
    İşletme sahibinin kendi yerleşim planını görüntülemesini ve güncellemesini sağlar.
    """
    serializer_class = BusinessLayoutSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'owned_business') and user.owned_business is not None:
            return BusinessLayout.objects.filter(business=user.owned_business)
        return BusinessLayout.objects.none()

    def get_object(self):
        """
        İşletme sahibinin tek olan yerleşim planını getirir.
        Bu metot, /api/layouts/{pk}/ gibi detay görünümleri için kullanılır.
        """
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset) 
        self.check_object_permissions(self.request, obj)
        return obj

    def list(self, request, *args, **kwargs):
        """
        GET /api/layouts/ isteğini karşılar. 
        Liste yerine, kullanıcıya ait tek bir yerleşim planı nesnesi döndürür.
        """
        user_business = get_user_business(request.user)
        if not user_business:
             return Response({"detail": "Yetkili bir işletmeniz bulunmuyor."}, status=status.HTTP_403_FORBIDDEN)
        
        instance, created = BusinessLayout.objects.get_or_create(business=user_business)
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)