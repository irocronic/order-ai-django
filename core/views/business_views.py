# core/views/business_views.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import Business
from ..serializers import BusinessSerializer
from rest_framework.exceptions import PermissionDenied, ValidationError

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
                # İşletme sahibinin kendi işletmesini döndür
                try:
                    # user.owned_business direkt erişimdir ve RelatedObjectDoesNotExist fırlatabilir.
                    # Business.objects.filter(owner=user) daha güvenlidir.
                    return Business.objects.filter(owner=user)
                except Business.DoesNotExist: # Bu aslında filter ile yakalanmaz, boş queryset döner.
                    return Business.objects.none()
            elif user.is_staff or user.is_superuser: # Admin veya Django staff kullanıcıları tümünü görebilir
                return Business.objects.all()
        # Diğer kimliği doğrulanmış kullanıcı tipleri (customer, staff olmayan personel) için boş queryset
        return Business.objects.none()

    def perform_create(self, serializer):
        # Yeni işletme oluşturulurken sahibi otomatik olarak istek yapan kullanıcı olmalı
        # ve user_type 'business_owner' olmalı.
        if self.request.user.user_type == 'business_owner':
            # Bir işletme sahibinin sadece bir işletmesi olabilir (OneToOneField)
            if hasattr(self.request.user, 'owned_business') and self.request.user.owned_business is not None:
                raise ValidationError({"detail": "Bu kullanıcıya ait zaten bir işletme mevcut."})
            serializer.save(owner=self.request.user, is_setup_complete=False) # Yeni işletme için kurulum tamamlanmadı
        else:
            raise PermissionDenied({"detail": "Sadece işletme sahipleri yeni işletme oluşturabilir."})

    @action(detail=True, methods=['post'], url_path='complete-setup', permission_classes=[IsAuthenticated])
    def complete_setup(self, request, pk=None):
        """
        İşletme sahibinin kurulum sihirbazını tamamladığını işaretler.
        """
        business = self.get_object()
        
        if business.owner != request.user:
            return Response({"detail": "Bu işlem için yetkiniz yok. Sadece işletme sahibi bu işlemi yapabilir."}, status=status.HTTP_403_FORBIDDEN)
        
        if business.is_setup_complete:
            return Response({"detail": "İşletme kurulumu zaten tamamlanmış."}, status=status.HTTP_400_BAD_REQUEST)

        business.is_setup_complete = True
        business.save(update_fields=['is_setup_complete'])
        serializer = self.get_serializer(business) # Güncellenmiş işletme bilgisini döndür
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