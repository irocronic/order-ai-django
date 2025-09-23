# core/views/business_views.py

from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from ..mixins import LimitCheckMixin
from ..models import Business, Table, BusinessLayout, LayoutElement
from ..serializers import BusinessSerializer, TableSerializer, BusinessLayoutSerializer, LayoutElementSerializer
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


    @action(detail=True, methods=['get', 'put'], url_path='payment-settings', permission_classes=[IsAuthenticated])
    def payment_settings(self, request, pk=None):
        business = self.get_object()
        # Sadece işletme sahibi kendi ayarlarını değiştirebilir
        if business.owner != request.user:
            raise PermissionDenied("Bu işlem için yetkiniz yok.")

        if request.method == 'GET':
            # GET isteğinde anahtarları ASLA göndermiyoruz. Sadece seçili sağlayıcıyı gönderiyoruz.
            return Response({
                'payment_provider': business.payment_provider,
                'provider_display': business.get_payment_provider_display(),
            })

        elif request.method == 'PUT':
            serializer = BusinessPaymentSettingsSerializer(business, data=request.data)
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response({
                    'status': 'success',
                    'message': 'Ödeme ayarları başarıyla güncellendi.',
                    'payment_provider': business.payment_provider,
                })


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
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset) 
        self.check_object_permissions(self.request, obj)
        return obj

    def list(self, request, *args, **kwargs):
        user_business = get_user_business(request.user)
        if not user_business:
             return Response({"detail": "Yetkili bir işletmeniz bulunmuyor."}, status=status.HTTP_403_FORBIDDEN)
        
        instance, created = BusinessLayout.objects.get_or_create(business=user_business)
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class LayoutElementViewSet(viewsets.ModelViewSet):
    """
    Yerleşim planı üzerindeki dekoratif öğeleri (metin, şekil) yönetir.
    """
    serializer_class = LayoutElementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_business = get_user_business(self.request.user)
        if user_business and hasattr(user_business, 'layout'):
            return LayoutElement.objects.filter(layout=user_business.layout)
        return LayoutElement.objects.none()

    def perform_create(self, serializer):
        user_business = get_user_business(self.request.user)
        if not (user_business and hasattr(user_business, 'layout')):
            raise PermissionDenied("Bu işlem için geçerli bir yerleşim planı bulunamadı.")
        serializer.save(layout=user_business.layout)

    @action(detail=False, methods=['post'], url_path='bulk-update')
    @transaction.atomic
    def bulk_update(self, request, *args, **kwargs):
        user_business = get_user_business(request.user)
        if not (user_business and hasattr(user_business, 'layout')):
            raise PermissionDenied("Bu işlem için geçerli bir yerleşim planı bulunamadı.")
        
        layout = user_business.layout
        elements_data = request.data
        
        if not isinstance(elements_data, list):
            raise ValidationError("İstek gövdesi bir liste olmalıdır.")

        existing_element_ids = set(self.get_queryset().values_list('id', flat=True))
        incoming_element_ids = {item.get('id') for item in elements_data if item.get('id') is not None}

        ids_to_delete = existing_element_ids - incoming_element_ids
        if ids_to_delete:
            LayoutElement.objects.filter(id__in=ids_to_delete).delete()

        for element_data in elements_data:
            element_id = element_data.get('id')
            if element_id in existing_element_ids:
                instance = LayoutElement.objects.get(id=element_id)
                serializer = self.get_serializer(instance, data=element_data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()
            else:
                serializer = self.get_serializer(data=element_data)
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)

        # HATA DÜZELTMESİ: İşlem bittikten sonra layout'a ait tüm elemanların
        # güncel listesini serializer'dan geçirerek geri döndürüyoruz.
        # Bu, Flutter tarafının yeni ID'leri almasını ve state'ini senkronize etmesini sağlar.
        updated_queryset = self.get_queryset()
        response_serializer = self.get_serializer(updated_queryset, many=True)
        return Response(response_serializer.data, status=status.HTTP_200_OK)