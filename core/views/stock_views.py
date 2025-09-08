# core/views/stock_views.py

from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound

from ..models import Stock, MenuItemVariant, StockMovement, Business, CustomUser as User, Ingredient, UnitOfMeasure, RecipeItem
from ..serializers import StockSerializer, StockMovementSerializer, IngredientSerializer, UnitOfMeasureSerializer, RecipeItemSerializer
from ..utils.order_helpers import get_user_business, PermissionKeys

class StockViewSet(viewsets.ModelViewSet):
    serializer_class = StockSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business:
            return Stock.objects.none()
        
        return Stock.objects.filter(
            variant__menu_item__business=user_business
        ).select_related('variant__menu_item__business', 'variant__menu_item__category')

    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business:
            raise PermissionDenied("Stok eklemek için yetkili bir işletmeniz bulunmuyor.")

        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            raise PermissionDenied("Stok ekleme yetkiniz yok.")

        variant = serializer.validated_data.get('variant')
        if not variant:
            raise ValidationError({"variant": "Stok için bir ürün varyantı seçilmelidir."})

        if variant.menu_item.business != user_business:
            raise PermissionDenied("Bu varyant sizin işletmenize ait değil, stok ekleyemezsiniz.")

        if Stock.objects.filter(variant=variant).exists():
            raise ValidationError({"variant": ["Bu varyant için zaten bir stok kaydı mevcut."]})

        with transaction.atomic():
            stock_instance = serializer.save()
            StockMovement.objects.create(
                stock=stock_instance,
                variant=stock_instance.variant,
                movement_type='INITIAL',
                quantity_change=stock_instance.quantity,
                quantity_before=0,
                quantity_after=stock_instance.quantity,
                user=user,
                description="İlk stok kaydı oluşturuldu."
            )

    def perform_update(self, serializer):
        user = self.request.user
        stock_instance = self.get_object()
        
        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            raise PermissionDenied("Stok güncelleme yetkiniz yok.")
        
        original_quantity = stock_instance.quantity
        updated_stock = serializer.save()
        new_quantity = updated_stock.quantity
        quantity_diff = new_quantity - original_quantity

        if quantity_diff != 0:
            StockMovement.objects.create(
                stock=updated_stock,
                variant=updated_stock.variant,
                movement_type='MANUAL_EDIT',
                quantity_change=quantity_diff,
                quantity_before=original_quantity,
                quantity_after=new_quantity,
                user=user,
                description="Stok miktarı admin/API üzerinden manuel olarak güncellendi."
            )

    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        user_business = get_user_business(user)
        if not user_business or obj.variant.menu_item.business != user_business:
            if not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Bu stok kaydına erişim yetkiniz yok.")
        return obj

    @action(detail=True, methods=['post'], url_path='adjust-stock')
    def adjust_stock(self, request, pk=None):
        stock_instance = self.get_object()
        user = request.user

        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            raise PermissionDenied("Stok ayarlama yetkiniz yok.")

        movement_type = request.data.get('movement_type')
        try:
            quantity_change_input = int(request.data.get('quantity_change', 0))
        except (ValueError, TypeError):
            return Response({'detail': 'Geçersiz miktar formatı.'}, status=status.HTTP_400_BAD_REQUEST)
        
        description = request.data.get('description', '')

        valid_manual_movement_types = ['ADDITION', 'WASTAGE', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT']
        if movement_type not in valid_manual_movement_types:
            return Response({'detail': f'Geçersiz hareket tipi. Kullanılabilir: {", ".join(valid_manual_movement_types)}'}, status=status.HTTP_400_BAD_REQUEST)

        if quantity_change_input <= 0:
            return Response({'detail': 'Miktar pozitif bir değer olmalıdır.'}, status=status.HTTP_400_BAD_REQUEST)

        quantity_to_apply = quantity_change_input
        if movement_type in ['WASTAGE', 'ADJUSTMENT_OUT']:
            quantity_to_apply = -quantity_change_input

        with transaction.atomic():
            current_stock = Stock.objects.select_for_update().get(id=stock_instance.id)
            original_quantity = current_stock.quantity
            
            if movement_type in ['WASTAGE', 'ADJUSTMENT_OUT'] and original_quantity < quantity_change_input:
                return Response({'detail': 'Çıkarılacak miktar mevcut stoktan fazla olamaz.'}, status=status.HTTP_400_BAD_REQUEST)

            new_quantity = original_quantity + quantity_to_apply
            if new_quantity < 0:
                new_quantity = 0 
            
            current_stock.quantity = new_quantity
            current_stock.save()

            StockMovement.objects.create(
                stock=current_stock,
                variant=current_stock.variant,
                movement_type=movement_type,
                quantity_change=quantity_to_apply,
                quantity_before=original_quantity,
                quantity_after=new_quantity,
                user=user,
                description=description
            )
        
        serializer = self.get_serializer(current_stock)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        stock_instance = self.get_object()
        user = request.user
        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            raise PermissionDenied("Stok geçmişini görüntüleme yetkiniz yok.")

        movements = stock_instance.movements.select_related(
            'variant__menu_item', 'user', 'related_order'
        ).all().order_by('-timestamp')
        
        page = self.paginate_queryset(movements)
        if page is not None:
            serializer = StockMovementSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = StockMovementSerializer(movements, many=True, context={'request': request})
        return Response(serializer.data)

class StockMovementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business:
            return StockMovement.objects.none()

        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            return StockMovement.objects.none()

        queryset = StockMovement.objects.filter(
            variant__menu_item__business=user_business
        ).select_related('stock', 'variant__menu_item', 'user', 'related_order')

        variant_id_param = self.request.query_params.get('variant_id')
        if variant_id_param:
            try:
                queryset = queryset.filter(variant_id=int(variant_id_param))
            except ValueError:
                return StockMovement.objects.none()

        movement_type_param = self.request.query_params.get('movement_type')
        if movement_type_param:
            queryset = queryset.filter(movement_type=movement_type_param)
        
        user_id_filter = self.request.query_params.get('user_id')
        if user_id_filter:
            try:
                queryset = queryset.filter(user_id=int(user_id_filter))
            except ValueError:
                return StockMovement.objects.none()

        start_date_str = self.request.query_params.get('start_date')
        end_date_str = self.request.query_params.get('end_date')

        if start_date_str:
            queryset = queryset.filter(timestamp__date__gte=start_date_str)
        if end_date_str:
            queryset = queryset.filter(timestamp__date__lte=end_date_str)
            
        return queryset.order_by('-timestamp')

class IngredientViewSet(viewsets.ModelViewSet):
    """
    Malzemeleri (ingredients) yönetmek için API endpoint'leri.
    """
    serializer_class = IngredientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)
        if user_business:
            # Sadece kullanıcının kendi işletmesine ait malzemeleri listele
            return Ingredient.objects.filter(business=user_business).select_related('unit')
        return Ingredient.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)
        
        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            raise PermissionDenied("Malzeme ekleme yetkiniz yok.")
            
        serializer.save(business=user_business)

    def perform_update(self, serializer):
        # get_object içindeki kontrol sayesinde bu instance'ın zaten
        # bu işletmeye ait olduğu doğrulanmış olur.
        user = self.request.user
        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            raise PermissionDenied("Malzeme güncelleme yetkiniz yok.")
            
        serializer.save()

class UnitOfMeasureViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Tüm ölçü birimlerini listeler.
    """
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [IsAuthenticated]
    queryset = UnitOfMeasure.objects.all()

# ================== YENİ EKLENEN BÖLÜM ==================
class RecipeItemViewSet(viewsets.ModelViewSet):
    """
    Bir ürün varyantına ait reçete kalemlerini (malzemeleri) yönetir.
    """
    serializer_class = RecipeItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)
        if not user_business:
            return RecipeItem.objects.none()

        queryset = RecipeItem.objects.filter(
            variant__menu_item__business=user_business
        ).select_related('ingredient', 'ingredient__unit')

        # Belirli bir varyantın reçetesini getirmek için filtreleme
        variant_id = self.request.query_params.get('variant_id')
        if variant_id:
            return queryset.filter(variant_id=variant_id)
            
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)
        variant = serializer.validated_data.get('variant')

        # Yetki kontrolü: Kullanıcı bu varyantın ait olduğu işletmede mi?
        if not user_business or variant.menu_item.business != user_business:
            raise PermissionDenied("Bu ürüne malzeme ekleme yetkiniz yok.")
            
        serializer.save()
# =======================================================