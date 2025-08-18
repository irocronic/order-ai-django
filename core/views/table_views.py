# core/views/table_views.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Max

# Gerekli importlar
from subscriptions.models import Subscription, Plan
from ..mixins import LimitCheckMixin
from ..models import Table, Business
from ..serializers import TableSerializer
from ..utils.order_helpers import get_user_business, PermissionKeys


class TableViewSet(LimitCheckMixin, viewsets.ModelViewSet):
    """
    Masaları yönetir. Giriş yapanın işletmesine ait tabloları döndürür.
    Yeni masa oluştururken abonelik limitlerini kontrol eder.
    """
    serializer_class = TableSerializer
    permission_classes = [IsAuthenticated]

    # Mixin için gerekli alanlar
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

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request, *args, **kwargs):
        """
        Belirtilen sayıda masayı toplu olarak oluşturur.
        Artık abonelik limitlerini de doğru şekilde kontrol eder.
        """
        user = request.user
        user_business = get_user_business(user)

        if not user_business:
            raise PermissionDenied("Toplu masa eklemek için yetkili bir işletmeniz bulunmuyor.")

        if not (user.user_type == 'business_owner' or (user.user_type == 'staff' and PermissionKeys.MANAGE_TABLES in user.staff_permissions)):
            raise PermissionDenied("Toplu masa ekleme yetkiniz yok.")
        
        try:
            count = int(request.data.get('count', 0))
        except (ValueError, TypeError):
            raise ValidationError({"count": "Lütfen geçerli bir sayı girin."})

        if not (0 < count <= 100):
            raise ValidationError({"count": "Masa adedi 1 ile 100 arasında olmalıdır."})

        # === GÜNCELLENEN LİMİT KONTROLÜ ===
        try:
            subscription = user_business.subscription
            # Hata burada: Limitler artık doğrudan 'subscription' üzerinde değil,
            # 'subscription.plan' üzerinde bulunuyor.
            if not subscription.plan:
                raise ValidationError({'detail': 'İşletme için aktif bir abonelik planı bulunamadı.', 'code': 'subscription_error'})
            
            # Doğru alan: subscription.plan nesnesinden limiti al
            limit = getattr(subscription.plan, self.limit_field_name)
            
            current_count = self.get_queryset().count()

            if current_count + count > limit:
                raise ValidationError({
                    'detail': f"Toplu olarak {count} adet masa eklenemiyor. "
                              f"Mevcut {current_count} masa ile birlikte limitiniz olan {limit} adedi aşmış olursunuz.",
                    'code': 'limit_reached'
                })
        except (Subscription.DoesNotExist, AttributeError):
              raise ValidationError({'detail': 'Abonelik planı bulunamadı veya limitler tanımlanmamış.', 'code': 'subscription_error'})
        # === /GÜNCELLENEN LİMİT KONTROLÜ ===

        highest_table_num = Table.objects.filter(business=user_business).aggregate(max_num=Max('table_number'))['max_num'] or 0

        tables_to_create = [
            Table(business=user_business, table_number=highest_table_num + i + 1)
            for i in range(count)
        ]

        created_tables = Table.objects.bulk_create(tables_to_create)
        serializer = self.get_serializer(created_tables, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # perform_update ve perform_destroy metotlarında değişiklik yok, aynı kalabilirler.
    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        user_business = get_user_business(user)

        if not user_business or instance.business != user_business:
            if not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Bu masayı güncelleme yetkiniz yok.")

        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_TABLES in user.staff_permissions)):
            if not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Masa güncelleme yetkiniz yok.")
        
        table_number = serializer.validated_data.get('table_number', instance.table_number)
        if table_number != instance.table_number and \
           Table.objects.filter(business=instance.business, table_number=table_number).exclude(pk=instance.pk).exists():
            raise ValidationError({"table_number": ["Bu masa numarası zaten işletmenizde kullanılıyor."]})
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business or instance.business != user_business:
            if not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Bu masayı silme yetkiniz yok.")

        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.MANAGE_TABLES in user.staff_permissions)):
            if not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Masa silme yetkiniz yok.")
        instance.delete()