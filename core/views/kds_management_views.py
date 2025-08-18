# core/views/kds_management_views.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

# Gerekli importlar eklendi
from ..mixins import LimitCheckMixin
from subscriptions.models import Subscription, Plan

from ..models import KDSScreen, Business
from ..serializers import KDSScreenSerializer
from ..utils.order_helpers import get_user_business, PermissionKeys


class KDSScreenViewSet(LimitCheckMixin, viewsets.ModelViewSet):
    """KDS Ekranlarını yönetir. Yeni ekran oluştururken limitleri kontrol eder."""
    serializer_class = KDSScreenSerializer
    permission_classes = [IsAuthenticated]

    # Mixin için gerekli alanlar
    limit_resource_name = "KDS Ekranı"
    limit_field_name = "max_kds_screens"

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)
        if user_business:
            return KDSScreen.objects.filter(business=user_business)
        return KDSScreen.objects.none()
    
    # --- GÜNCELLENMİŞ CREATE METODU ---
    def create(self, request, *args, **kwargs):
        is_many = isinstance(request.data, list)
        if not is_many:
            # Eğer tek bir nesne oluşturuluyorsa, LimitCheckMixin'in devraldığı
            # standart create metodunu çağır. Bu metot, perform_create'i tetikleyecektir.
            return super().create(request, *args, **kwargs)

        # Eğer bir liste geliyorsa, toplu oluşturma işlemi yap
        user_business = get_user_business(request.user)
        if not user_business:
            raise PermissionDenied("KDS ekranı oluşturmak için yetkili bir işletmeniz bulunmuyor.")
            
        # Toplu oluşturma için yetki kontrolü
        if not (request.user.user_type == 'business_owner' or (request.user.user_type == 'staff' and PermissionKeys.MANAGE_KDS_SCREENS in request.user.staff_permissions)):
            raise PermissionDenied("KDS ekranı oluşturma yetkiniz yok.")

        # Toplu oluşturma için limit kontrolü
        try:
            subscription = user_business.subscription
            if not subscription.plan:
                raise ValidationError({'detail': 'İşletme için aktif bir abonelik planı bulunamadı.', 'code': 'subscription_error'})
            
            # Limiti Plan modelinden al
            limit = getattr(subscription.plan, self.limit_field_name)
            current_count = self.get_queryset().count()
            requested_count = len(request.data)

            if current_count + requested_count > limit:
                raise ValidationError({
                    'detail': f"Toplu olarak {requested_count} adet KDS ekranı eklenemiyor. "
                              f"Mevcut {current_count} adet ile birlikte limitiniz olan {limit} adedi aşmış olursunuz.",
                    'code': 'limit_reached'
                })
        except (Subscription.DoesNotExist, AttributeError):
              raise ValidationError({'detail': 'Abonelik planı bulunamadı veya limitler tanımlanmamış.', 'code': 'subscription_error'})

        # Gelen veriye business ID'yi ekle
        for item in request.data:
            item['business'] = user_business.id
        
        serializer = self.get_serializer(data=request.data, many=True)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            if 'name' in str(e):
                return Response({"detail": "Bu isimde bir KDS ekranı zaten mevcut."}, status=status.HTTP_400_BAD_REQUEST)
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    # --- /GÜNCELLENMİŞ CREATE METODU ---

    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)
        
        if not user_business:
            raise PermissionDenied("KDS ekranı oluşturmak için yetkili bir işletmeniz bulunmuyor.")
        
        if not (user.user_type == 'business_owner' or (user.user_type == 'staff' and PermissionKeys.MANAGE_KDS_SCREENS in user.staff_permissions)):
            raise PermissionDenied("KDS ekranı oluşturma yetkiniz yok.")
        
        # Eğer tekli oluşturma ise LimitCheckMixin zaten kontrolü yapar.
        # Bu metot hem tekli hem de toplu oluşturma için çalışır.
        if isinstance(serializer.validated_data, list):
            # Toplu oluşturmada business zaten `create` metodu içinde eklendi.
            serializer.save()
        else: 
            # Tekli oluşturmada LimitCheckMixin'in çalışabilmesi için business'ı burada atıyoruz.
            serializer.save(business=user_business)

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        user_business = get_user_business(user)

        if not user_business or instance.business != user_business:
            if not user.is_superuser:
                raise PermissionDenied("Bu KDS ekranını güncelleme yetkiniz yok (farklı işletme).")

        if not (user.user_type == 'business_owner' or (user.user_type == 'staff' and 'manage_kds_screens' in user.staff_permissions) or user.is_superuser):
            raise PermissionDenied("KDS ekranı güncelleme yetkiniz yok.")
        
        # business ID'yi payload'a ekleyerek serializer'ın validate metodunun çalışmasını sağlıyoruz.
        serializer.save(business=user_business)

    def perform_destroy(self, instance):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business or instance.business != user_business:
            if not user.is_superuser:
                raise PermissionDenied("Bu KDS ekranını silme yetkiniz yok (farklı işletme).")
        
        if not (user.user_type == 'business_owner' or (user.user_type == 'staff' and 'manage_kds_screens' in user.staff_permissions) or user.is_superuser):
            raise PermissionDenied("KDS ekranı silme yetkiniz yok.")
        
        instance.delete()

    def get_permissions(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            raise PermissionDenied("Bu işlem için kimlik doğrulaması gereklidir.")
        
        if self.action in ['list', 'retrieve', 'create', 'update', 'partial_update', 'destroy']:
            if user.user_type == 'business_owner' or \
               (user.user_type == 'staff' and 'manage_kds_screens' in user.staff_permissions) or \
               user.is_superuser:
                return [IsAuthenticated()]
            raise PermissionDenied(f"KDS ekranı için '{self.action}' yetkiniz yok.")
        
        return super().get_permissions()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        context['user_business'] = get_user_business(self.request.user)
        return context