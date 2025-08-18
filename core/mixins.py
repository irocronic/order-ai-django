# core/mixins.py

from rest_framework.exceptions import ValidationError
# --- GÜNCELLENEN IMPORT ---
# Artık Plan modelini de import ediyoruz, çünkü limitler orada tutuluyor.
from subscriptions.models import Subscription, Plan
# --- /GÜNCELLENEN IMPORT ---

class LimitCheckMixin:
    """
    Yeni bir nesne oluşturulmadan önce işletmenin abonelik planı limitlerini kontrol eden mixin.
    Bu mixin'i kullanan ViewSet'lerde 'limit_resource_name' ve 'limit_field_name' tanımlanmalıdır.
    """
    limit_resource_name = None
    limit_field_name = None # Örn: 'max_tables', 'max_staff'

    def perform_create(self, serializer):
        if not self.limit_resource_name or not self.limit_field_name:
            raise NotImplementedError("LimitCheckMixin için 'limit_resource_name' ve 'limit_field_name' tanımlanmalıdır.")

        business = serializer.validated_data.get('business')
        if not business:
            user = self.request.user
            if hasattr(user, 'owned_business'):
                business = getattr(user, 'owned_business', None)
            elif hasattr(user, 'associated_business'):
                business = getattr(user, 'associated_business', None)

        if not business:
            raise ValidationError({'detail': 'İşlem için işletme bilgisi bulunamadı.'})

        try:
            # --- GÜNCELLENEN LİMİT KONTROL MANTIĞI ---
            # 1. İşletmenin aboneliğini bul.
            subscription = business.subscription
            # 2. Aboneliğe bağlı bir Plan olup olmadığını kontrol et.
            if not subscription.plan:
                raise ValidationError({'detail': 'İşletme için aktif bir abonelik planı bulunamadı.', 'code': 'subscription_error'})
            # 3. Limiti, Subscription'dan değil, ilişkili Plan nesnesinden al.
            limit = getattr(subscription.plan, self.limit_field_name)
            # --- /GÜNCELLENEN LİMİT KONTROL MANTIĞI ---
        except (Subscription.DoesNotExist, Plan.DoesNotExist, AttributeError):
            raise ValidationError({'detail': 'Abonelik planı bulunamadı veya limitler tanımlanmamış.', 'code': 'subscription_error'})

        # Bu kısım doğru ve değişmeden kalıyor.
        current_count = self.get_queryset().filter(business=business).count()

        if current_count >= limit:
            raise ValidationError({
                'detail': f"{self.limit_resource_name} oluşturma limitinize ({limit}) ulaştınız. Lütfen paketinizi yükseltin.",
                'code': 'limit_reached'
            })
        
        # Eğer serializer'da business bilgisi yoksa, buradan ekleyerek kaydet
        if 'business' not in serializer.validated_data:
            serializer.save(business=business)
        else:
            serializer.save()