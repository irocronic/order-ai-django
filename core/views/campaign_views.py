# core/views/campaign_views.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.models.deletion import ProtectedError # ProtectedError'u import et

from ..models import CampaignMenu, MenuItem, Category, Business
from ..serializers import CampaignMenuSerializer
from ..permissions import IsBusinessOwnerAndOwnerOfObject # Önceki yanıtta IsBusinessOwnerAndOwnerOfStaff olarak düzeltilmişti, bu doğru olan
from ..utils.order_helpers import get_user_business, PermissionKeys
import logging # Logging için import eklendi

logger = logging.getLogger(__name__)

class CampaignMenuViewSet(viewsets.ModelViewSet):
    serializer_class = CampaignMenuSerializer
    permission_classes = [IsAuthenticated] # Genel kimlik doğrulaması

    def get_queryset(self):
        user = self.request.user
        business = get_user_business(user)
        if business:
            # Sadece aktif kampanyaları getirmek isterseniz:
            # return CampaignMenu.objects.filter(business=business, is_active=True).select_related('bundle_menu_item').prefetch_related('campaign_items__menu_item', 'campaign_items__variant')
            return CampaignMenu.objects.filter(business=business).select_related('bundle_menu_item').prefetch_related('campaign_items__menu_item', 'campaign_items__variant')
        # Admin tüm kampanyaları görebilir mi? (Opsiyonel)
        # if user.is_superuser:
        # return CampaignMenu.objects.all()
        return CampaignMenu.objects.none()

    def get_permissions(self):
        """
        Action'a göre izinleri ayarla.
        """
        # Listeleme ve görüntüleme için daha esnek izinler veya sadece kimlik doğrulanmış olma.
        # Create, Update, Destroy için ise işletme sahibi veya manage_campaigns izni.
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        # Diğer tüm action'lar (create, update, destroy) için IsBusinessOwnerAndOwnerOfObject kullanılır.
        # Bu izin sınıfı, nesnenin kendi işlletmesine ait olduğunu kontrol eder.
        return [IsAuthenticated(), IsBusinessOwnerAndOwnerOfObject()] 

    @transaction.atomic
    def perform_create(self, serializer):
        user_business = get_user_business(self.request.user)
        if not user_business:
            raise serializers.ValidationError("Bu işlem için yetkili bir işletmeniz bulunmuyor.")

        # Kullanıcının kampanya oluşturma yetkisi olmalı
        user = self.request.user
        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_CAMPAIGNS in user.staff_permissions)):
            raise serializers.ValidationError({"detail": "Kampanya oluşturma yetkiniz yok."})

        # Kampanya için özel bir menü öğesi oluştur/güncelle
        campaign_category, _ = Category.objects.get_or_create(
            business=user_business,
            name="Kampanyalar",
            defaults={'parent': None} 
        )

        bundle_menu_item = MenuItem.objects.create(
            business=user_business,
            name=serializer.validated_data.get('name') + " (Kampanya Paketi)",
            description=serializer.validated_data.get('description', ''),
            category=campaign_category,
            image=serializer.validated_data.get('image'),
            is_campaign_bundle=True, # Bu önemli
            # Fiyatı MenuItem'dan değil, CampaignMenu'den alacağız, bu yüzden price alanı burada null kalabilir.
        )

        campaign = serializer.save(business=user_business, bundle_menu_item=bundle_menu_item)
        logger.info(f"Yeni kampanya oluşturuldu: {campaign.name} (ID: {campaign.id}), İlişkili MenuItem: {bundle_menu_item.id}")


    @transaction.atomic
    def perform_update(self, serializer):
        user_business = get_user_business(self.request.user)
        instance = self.get_object() # Bu, object-level permission'ı da kontrol eder (IsBusinessOwnerAndOwnerOfObject)

        user = self.request.user
        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_CAMPAIGNS in user.staff_permissions)):
            raise serializers.ValidationError({"detail": "Kampanya güncelleme yetkiniz yok."})


        if instance.business != user_business:
             # Bu durum normalde IsBusinessOwnerAndOwnerOfObject tarafından yakalanmalı ama ek kontrol.
            raise serializers.ValidationError({"detail": "Bu kampanyayı güncelleme yetkiniz yok (işletme eşleşmiyor)."})

        # Bundle MenuItem'ı güncelle (isim, açıklama, görsel)
        bundle_item = instance.bundle_menu_item
        if bundle_item:
            bundle_item.name = serializer.validated_data.get('name', instance.name) + " (Kampanya Paketi)"
            bundle_item.description = serializer.validated_data.get('description', instance.description or '')
            bundle_item.image = serializer.validated_data.get('image', instance.image)
            # is_active alanı CampaignMenu'den gelir, bundle_menu_item'ın is_active'i CampaignMenu'ninkiyle senkronize edilebilir.
            bundle_item.is_active = serializer.validated_data.get('is_active', instance.is_active)
            bundle_item.save()
            logger.info(f"Kampanya {instance.id} için ilişkili MenuItem {bundle_item.id} güncellendi.")
        else:
            # Eğer bir şekilde bundle_menu_item oluşmamışsa (olmamalı), yeniden oluştur.
            # Bu durum nadir olmalı, create sırasında oluşturuluyor.
            # Normalde, bu bir hata durumunu işaret eder ve düzeltilmesi gerekir.
            logger.error(f"Kampanya {instance.id} için ilişkili bundle_menu_item bulunamadı. Yeniden oluşturuluyor.")
            campaign_category, _ = Category.objects.get_or_create(
                business=user_business, name="Kampanyalar", defaults={'parent': None}
            )
            new_bundle_item = MenuItem.objects.create(
                business=user_business,
                name=serializer.validated_data.get('name', instance.name) + " (Kampanya Paketi)",
                description=serializer.validated_data.get('description', instance.description or ''),
                category=campaign_category,
                image=serializer.validated_data.get('image', instance.image),
                is_campaign_bundle=True,
                is_active=serializer.validated_data.get('is_active', instance.is_active) # Yeni MenuItem'ın aktifliğini de CampaignMenu ile senkronize et
            )
            serializer.validated_data['bundle_menu_item'] = new_bundle_item
            logger.info(f"Kampanya {instance.id} için yeni bundle_menu_item {new_bundle_item.id} oluşturuldu.")


        serializer.save()
        logger.info(f"Kampanya {instance.name} (ID: {instance.id}) başarıyla güncellendi.")


    @transaction.atomic
    def perform_destroy(self, instance: CampaignMenu):
        user = self.request.user
        user_business = get_user_business(user)

        # Kullanıcının kampanya silme yetkisi olmalı
        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_CAMPAIGNS in user.staff_permissions)):
            raise serializers.ValidationError({"detail": "Kampanya silme yetkiniz yok."})

        if not user_business or instance.business != user_business:
            # Bu durum normalde IsBusinessOwnerAndOwnerOfObject tarafından yakalanmalı ama ek kontrol.
            raise serializers.ValidationError({"detail": "Bu kampanyayı silme yetkiniz yok (işletme eşleşmiyor)."})

        # İlişkili bundle MenuItem'ı bul
        bundle_menu_item = instance.bundle_menu_item

        if bundle_menu_item:
            try:
                # MenuItem'ı silmek yerine pasif yap
                bundle_menu_item.is_active = False
                bundle_menu_item.save(update_fields=['is_active'])
                logger.info(f"Kampanya {instance.name} (ID: {instance.id}) ile ilişkili MenuItem {bundle_menu_item.id} siparişlerde kullanıldığı için pasif yapıldı, silinmedi.")
            except ProtectedError as e:
                logger.error(f"Kampanya silinirken ilişkili MenuItem ({bundle_menu_item.id}) ProtectedError: {e}. MenuItem pasifleştirilemedi, kampanya silme iptal edildi.")
                raise serializers.ValidationError({"detail": "Kampanya silinemedi. İlişkili ürünler aktif siparişlerde kullanılıyor. Ürünler pasifleştirilemediği için kampanya silinemiyor."})
            except Exception as e:
                logger.error(f"Kampanya silinirken ilişkili MenuItem ({bundle_menu_item.id}) pasifleştirme hatası: {e}. Kampanya silme iptal edildi.")
                raise serializers.ValidationError({"detail": f"Kampanya silinemedi. İlişkili ürün pasifleştirilirken bir hata oluştu: {e}"})
        
        # Kampanya objesini sil
        instance.delete()
        logger.info(f"Kampanya {instance.name} (ID: {instance.id}) başarıyla silindi.")