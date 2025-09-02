# core/views/menu_views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db.models import ProtectedError, Prefetch
import logging

from django.utils import timezone
from django.db.models import Q

# Gerekli importlar
from ..mixins import LimitCheckMixin
from subscriptions.models import Subscription, Plan

from ..models import Category, MenuItem, MenuItemVariant, Business, KDSScreen, CampaignMenu, OrderItem
from ..serializers import CategorySerializer, MenuItemSerializer, MenuItemVariantSerializer
from ..utils.order_helpers import get_user_business, PermissionKeys
from ..permissions import IsBusinessOwnerAndOwnerOfObject

from django.db import transaction
from templates.models import CategoryTemplate # YENİ IMPORT

from rest_framework.decorators import action

logger = logging.getLogger(__name__)

# === GÜNCELLENMESİ GEREKEN VIEWSET BURASI ===
class CategoryViewSet(LimitCheckMixin, viewsets.ModelViewSet):
    """Kategorileri yönetir. Yeni kategori oluştururken limitleri kontrol eder."""
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    limit_resource_name = "Kategori"
    limit_field_name = "max_categories"

    # --- GÜNCELLENEN METOT ---
    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)

        if user_business:
            return Category.objects.filter(business=user_business).select_related('parent', 'assigned_kds')
        
        # Eğer kullanıcı bir işletmeye bağlı değilse (ve admin değilse), boş liste döner.
        return Category.objects.none()
    # --- /GÜNCELLENEN METOT ---

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        user_business = get_user_business(user)

        if not user_business or instance.business != user_business:
            if not user.is_superuser:
                raise PermissionDenied("Bu kategoriyi güncelleme yetkiniz yok.")

        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_MENU in user.staff_permissions) or
                user.is_superuser):
            raise PermissionDenied("Kategori güncelleme yetkiniz yok.")

        assigned_kds_instance = serializer.validated_data.get('assigned_kds', instance.assigned_kds)

        if assigned_kds_instance and assigned_kds_instance.business != instance.business:
            raise ValidationError({
                'assigned_kds': f"Seçilen KDS ekranı ('{assigned_kds_instance.name}') bu kategorinin işletmesine ('{instance.business.name}') ait değil."
            })
        
        parent_category = serializer.validated_data.get('parent')
        if parent_category and parent_category.business != instance.business:
            raise ValidationError({
                'parent': f"Seçilen üst kategori ('{parent_category.name}') bu kategorinin işletmesine ait değil."
            })

        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business or instance.business != user_business:
            if not user.is_superuser:
                raise PermissionDenied("Bu kategoriyi silme yetkiniz yok.")

        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_MENU in user.staff_permissions) or
                user.is_superuser):
            raise PermissionDenied("Kategori silme yetkiniz yok.")
        
        logger.info(f"Category ID {instance.id} ('{instance.name}') siliniyor.")
        instance.delete()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        context['user_business'] = get_user_business(self.request.user)
        return context

    # YENİ ACTION
    @action(detail=False, methods=['post'], url_path='create-from-template')
    @transaction.atomic
    def create_from_template(self, request, *args, **kwargs):
        user_business = get_user_business(request.user)
        template_ids = request.data.get('template_ids', [])

        if not isinstance(template_ids, list):
            raise ValidationError({"detail": "template_ids bir liste olmalıdır."})

        # Abonelik limitlerini kontrol et
        try:
            subscription = user_business.subscription
            if not subscription.plan:
                raise ValidationError({'detail': 'Aktif bir abonelik planı bulunamadı.', 'code': 'subscription_error'})
            limit = getattr(subscription.plan, self.limit_field_name)
            current_count = self.get_queryset().count()
            if current_count + len(template_ids) > limit:
                raise ValidationError({
                    'detail': f"Şablonlarla birlikte kategori limitinizi ({limit}) aşıyorsunuz.",
                    'code': 'limit_reached'
                })
        except (Subscription.DoesNotExist, AttributeError):
            raise ValidationError({'detail': 'Abonelik planı bulunamadı.', 'code': 'subscription_error'})

        templates = CategoryTemplate.objects.filter(id__in=template_ids)
        created_categories = []
        for template in templates:
            # Aynı isimde kategori varsa oluşturma, mevcut olanı kullan
            category, created = Category.objects.get_or_create(
                business=user_business,
                name=template.name,
                defaults={'parent': None}
            )
            if created:
                created_categories.append(category)

        serializer = self.get_serializer(created_categories, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# Diğer ViewSet'ler doğru olduğu için aynı kalıyor
class MenuItemViewSet(LimitCheckMixin, viewsets.ModelViewSet):
    """Menü öğelerini yönetir. Yeni ürün oluştururken limitleri kontrol eder."""
    serializer_class = MenuItemSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwnerAndOwnerOfObject]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    limit_resource_name = "Ürün"
    limit_field_name = "max_menu_items"
    
    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)
        if not user_business:
            return MenuItem.objects.none()

        now = timezone.now().date()
        valid_campaign_q = Q(
            business=user_business,
            is_active=True
        ) & (
            Q(start_date__isnull=True) | Q(start_date__lte=now)
        ) & (
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )
        
        valid_campaign_menu_item_ids = CampaignMenu.objects.filter(
            valid_campaign_q,
            bundle_menu_item__isnull=False
        ).values_list('bundle_menu_item_id', flat=True)

        queryset = MenuItem.objects.filter(
            Q(business=user_business, is_active=True) & 
            (Q(is_campaign_bundle=False) | Q(id__in=list(valid_campaign_menu_item_ids)))
        ).select_related(
            'category', 
            'category__assigned_kds', 
            'represented_campaign'
        ).prefetch_related(
            Prefetch('variants', queryset=MenuItemVariant.objects.select_related('stock'))
        )
        
        return queryset.order_by('category__name', 'name')

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        user_business = get_user_business(user)

        if not user_business or instance.business != user_business:
            if not user.is_superuser:
                raise PermissionDenied("Bu menü öğesini güncelleme yetkiniz yok.")

        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_MENU in user.staff_permissions) or
                user.is_superuser):
            raise PermissionDenied("Menü öğesi güncelleme yetkiniz yok.")

        category_instance = serializer.validated_data.get('category', instance.category)
        if category_instance and category_instance.business != instance.business:
            raise ValidationError({"category_id": ["Seçilen kategori bu işletmeye ait değil."]})

        serializer.save()

    def perform_destroy(self, instance: MenuItem):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business or instance.business != user_business:
            if not user.is_superuser:
                raise PermissionDenied("Bu menü öğesini silme yetkiniz yok.")
        
        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_MENU in user.staff_permissions) or
                user.is_superuser):
            raise PermissionDenied("Menü öğesi silme yetkiniz yok.")

        if instance.order_items.exists():
            instance.is_active = False
            instance.save(update_fields=['is_active'])
            logger.info(f"MenuItem ID {instance.id} ('{instance.name}') siparişlerde kullanıldığı için pasif yapıldı.")
        else:
            logger.info(f"MenuItem ID {instance.id} ('{instance.name}') hiçbir siparişte kullanılmadığı için siliniyor.")
            try:
                instance.delete()
            except ProtectedError as e:
                logger.error(f"MenuItem ID {instance.id} ('{instance.name}') beklenmedik bir ProtectedError ile karşılaştı: {e}. Pasif yapılıyor.")
                instance.is_active = False
                instance.save(update_fields=['is_active'])

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

class MenuItemVariantViewSet(LimitCheckMixin, viewsets.ModelViewSet):
    """Menü öğesi varyantlarını yönetir. Yeni varyant oluştururken limitleri kontrol eder."""
    serializer_class = MenuItemVariantSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwnerAndOwnerOfObject]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    limit_resource_name = "Varyant"
    limit_field_name = "max_variants"

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)
        
        base_queryset = MenuItemVariant.objects.filter(
            menu_item__is_active=True
        ).select_related(
            'menu_item__business', 
            'menu_item__category',
            'menu_item__category__assigned_kds'
        )
        
        if not user_business:
            if user.is_superuser:
                menu_item_id_param_super = self.request.query_params.get('menu_item')
                if menu_item_id_param_super:
                    try:
                        return base_queryset.filter(menu_item_id=int(menu_item_id_param_super))
                    except ValueError:
                        return MenuItemVariant.objects.none()
                return base_queryset.all()
            return MenuItemVariant.objects.none()
            
        queryset = base_queryset.filter(menu_item__business=user_business)
        menu_item_id_param = self.request.query_params.get('menu_item')
        if menu_item_id_param:
            try:
                return queryset.filter(menu_item_id=int(menu_item_id_param))
            except ValueError:
                return MenuItemVariant.objects.none()
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)
        if not user_business:
            raise PermissionDenied("Varyant eklemek için yetkili bir işletmeniz bulunmuyor.")

        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_MENU in user.staff_permissions)):
            raise PermissionDenied("Varyant ekleme yetkiniz yok.")
        
        try:
            subscription = user_business.subscription
            if not subscription.plan:
                raise ValidationError({'detail': 'İşletme için aktif bir abonelik planı bulunamadı.', 'code': 'subscription_error'})
            
            limit = getattr(subscription.plan, self.limit_field_name)
            current_count = MenuItemVariant.objects.filter(menu_item__business=user_business).count()

            if current_count >= limit:
                raise ValidationError({
                    'detail': f"{self.limit_resource_name} oluşturma limitinize ({limit}) ulaştınız. Lütfen paketinizi yükseltin.",
                    'code': 'limit_reached'
                })
        except (Subscription.DoesNotExist, AttributeError):
              raise ValidationError({'detail': 'Abonelik planı bulunamadı veya limitler tanımlanmamış.', 'code': 'subscription_error'})
        
        menu_item_instance = serializer.validated_data.get('menu_item')
        if not menu_item_instance:
            raise ValidationError({"menu_item": "Varyant bir menü öğesine bağlı olmalıdır."})

        if menu_item_instance.business != user_business:
            raise PermissionDenied("Bu menü öğesi sizin işletmenize ait değil, varyant ekleyemezsiniz.")
        
        if not menu_item_instance.is_active:
            raise ValidationError({"menu_item": "Pasif bir menü öğesine varyant ekleyemezsiniz."})
        
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        user_business = get_user_business(user)

        if not user_business or instance.menu_item.business != user_business:
            if not user.is_superuser:
                raise PermissionDenied("Bu varyantı güncelleme yetkiniz yok.")
        
        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_MENU in user.staff_permissions) or
                user.is_superuser):
            raise PermissionDenied("Varyant güncelleme yetkiniz yok.")
        
        if not instance.menu_item.is_active:
            raise ValidationError({"detail": "Pasif bir menü öğesinin varyantı güncellenemez."})

        serializer.save()

    def perform_destroy(self, instance: MenuItemVariant):
        user = self.request.user
        user_business = get_user_business(user)
        if not user_business or instance.menu_item.business != user_business:
            if not user.is_superuser:
                raise PermissionDenied("Bu varyantı silme yetkiniz yok.")
        
        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_MENU in user.staff_permissions) or
                user.is_superuser):
            raise PermissionDenied("Varyant silme yetkiniz yok.")

        try:
            logger.info(f"MenuItemVariant ID {instance.id} ('{instance.name}') siliniyor.")
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                f"'{instance.name}' varyantı ({instance.menu_item.name} ürününe ait) mevcut veya geçmiş siparişlerde kullanıldığı için silinemez. "
                "Bu varyantı kullanımdan kaldırmak için ana menü öğesini pasifleştirebilirsiniz."
            )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context