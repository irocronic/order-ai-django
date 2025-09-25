# core/views/table_views.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Max
# Gerekli importlar eklendi
from django.db import transaction
from ..utils.order_helpers import get_user_business

# Gerekli importlar
from subscriptions.models import Subscription, Plan
from ..mixins import LimitCheckMixin
from ..models import Table, Business
from ..serializers import TableSerializer
from ..utils.order_helpers import PermissionKeys


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

    # +++ YENİ EKLENEN METOT +++
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

        # incoming id'leri set haline getir
        incoming_ids = {item.get('id') for item in tables_data if item.get('id') is not None}
        if not incoming_ids:
            return Response({'detail': 'İstek içinde güncellenecek geçerli id bulunamadı.'}, status=status.HTTP_400_BAD_REQUEST)

        tables_to_update = Table.objects.filter(id__in=incoming_ids, business=user_business)

        existing_ids = set(tables_to_update.values_list('id', flat=True))
        missing_ids = list(incoming_ids - existing_ids)
        if missing_ids:
            # Daha açıklayıcı geri dönüş: eksik id'leri de döndürüyoruz.
            return Response({
                'detail': 'Bazı masalar bulunamadı veya işletmenize ait değil.',
                'missing_ids': missing_ids
            }, status=status.HTTP_403_FORBIDDEN)
            
        layout = user_business.layout

        with transaction.atomic():
            id_to_table = {t.id: t for t in tables_to_update}
            for data in tables_data:
                table_id = data.get('id')
                table = id_to_table.get(table_id)
                if table:
                    table.pos_x = data.get('pos_x')
                    table.pos_y = data.get('pos_y')
                    table.rotation = data.get('rotation', 0.0)
                    table.layout = layout
                    table.save(update_fields=['pos_x', 'pos_y', 'rotation', 'layout'])

        return Response({'status': 'success', 'message': f'{len(tables_data)} masanın pozisyonu güncellendi.'}, status=status.HTTP_200_OK)

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