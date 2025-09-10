# core/views/stock_views.py

from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.db.models import F
from decimal import Decimal
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from django.utils import timezone
from django.db.models.deletion import ProtectedError
import logging

from ..models import (
    MenuItemVariant, Business, CustomUser as User,
    Ingredient, UnitOfMeasure, RecipeItem, IngredientStockMovement,
    Supplier, PurchaseOrder, PurchaseOrderItem
)
from ..serializers import (
    IngredientSerializer,
    UnitOfMeasureSerializer, RecipeItemSerializer, IngredientStockMovementSerializer,
    SupplierSerializer, PurchaseOrderSerializer
)
from ..utils.order_helpers import get_user_business, PermissionKeys
from ..tasks import send_manual_low_stock_email_task # YENİ: Manuel görev import edildi

logger = logging.getLogger(__name__)


class IngredientViewSet(viewsets.ModelViewSet):
    serializer_class = IngredientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)
        if user_business:
            return Ingredient.objects.filter(business=user_business).select_related('unit', 'supplier')
        return Ingredient.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)
        
        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            raise PermissionDenied("Malzeme ekleme yetkiniz yok.")
            
        serializer.save(business=user_business)

    def perform_update(self, serializer):
        user = self.request.user
        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            raise PermissionDenied("Malzeme güncelleme yetkiniz yok.")
            
        serializer.save()
        
    @action(detail=True, methods=['post'], url_path='adjust-stock')
    @transaction.atomic
    def adjust_stock(self, request, pk=None):
        ingredient = self.get_object()
        user = request.user

        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            raise PermissionDenied("Malzeme stoğunu ayarlama yetkiniz yok.")

        movement_type = request.data.get('movement_type')
        try:
            quantity_change = Decimal(request.data.get('quantity_change', '0'))
        except (ValueError, TypeError):
            raise ValidationError({'detail': 'Geçersiz miktar formatı.'})
        
        description = request.data.get('description', '')

        valid_manual_types = ['ADDITION', 'WASTAGE', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT']
        if movement_type not in valid_manual_types:
            raise ValidationError({'detail': f'Geçersiz hareket tipi. Kullanılabilir: {", ".join(valid_manual_types)}'})

        if quantity_change <= 0:
            raise ValidationError({'detail': 'Miktar pozitif bir değer olmalıdır.'})

        quantity_to_apply = quantity_change
        if movement_type in ['WASTAGE', 'ADJUSTMENT_OUT']:
            quantity_to_apply = -quantity_change

        ingredient_to_update = Ingredient.objects.select_for_update().get(pk=ingredient.pk)
        original_quantity = ingredient_to_update.stock_quantity

        if quantity_to_apply < 0 and original_quantity < abs(quantity_to_apply):
            raise ValidationError({'detail': 'Çıkarılacak miktar mevcut stoktan fazla olamaz.'})
            
        new_quantity = original_quantity + quantity_to_apply

        # +++++++++++++++ YENİ KONTROL: Bayrağı sıfırla +++++++++++++++
        # Stok artırılıyor ve yeni miktar uyarı eşiğinin üstüne çıkıyorsa,
        # düşük stok bildirim bayrağını sıfırla ki yeniden düştüğünde bildirim gönderilebilsin
        update_fields_for_save = ['stock_quantity']
        if (quantity_to_apply > 0 and 
            ingredient_to_update.alert_threshold is not None and 
            new_quantity > ingredient_to_update.alert_threshold):
            if ingredient_to_update.low_stock_notification_sent:
                ingredient_to_update.low_stock_notification_sent = False
                update_fields_for_save.append('low_stock_notification_sent')
                logger.info(
                    f"Malzeme '{ingredient_to_update.name}' için düşük stok bildirim bayrağı sıfırlandı. "
                    f"Önceki stok: {original_quantity}, Yeni stok: {new_quantity}, "
                    f"Uyarı eşiği: {ingredient_to_update.alert_threshold}"
                )
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

        IngredientStockMovement.objects.create(
            ingredient=ingredient_to_update,
            movement_type=movement_type,
            quantity_change=quantity_to_apply,
            quantity_before=original_quantity,
            quantity_after=new_quantity,
            user=user,
            description=description
        )

        ingredient_to_update.stock_quantity = new_quantity
        ingredient_to_update.save(update_fields=update_fields_for_save)
        
        ingredient_to_update.refresh_from_db()
        serializer = self.get_serializer(ingredient_to_update)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        ingredient = self.get_object()
        movements = ingredient.movements.select_related('user').order_by('-timestamp')
        
        page = self.paginate_queryset(movements)
        if page is not None:
            serializer = IngredientStockMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = IngredientStockMovementSerializer(movements, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='assign-supplier')
    def assign_supplier(self, request):
        """
        Birden fazla malzemeye aynı anda tedarikçi atar.
        Request data: {
            'supplier_id': 123,
            'ingredient_ids': [1, 2, 3, 4]
        }
        """
        user = request.user
        user_business = get_user_business(user)
        
        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            raise PermissionDenied("Malzeme-tedarikçi ataması yapma yetkiniz yok.")

        supplier_id = request.data.get('supplier_id')
        ingredient_ids = request.data.get('ingredient_ids', [])

        if not supplier_id or not ingredient_ids:
            return Response(
                {'detail': 'supplier_id ve ingredient_ids parametreleri gereklidir.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            supplier = Supplier.objects.get(id=supplier_id, business=user_business)
            
            ingredients = Ingredient.objects.filter(
                id__in=ingredient_ids, 
                business=user_business
            )
            
            if ingredients.count() != len(ingredient_ids):
                return Response(
                    {'detail': 'Bazı malzemeler bulunamadı veya erişim yetkiniz yok.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            updated_count = ingredients.update(supplier=supplier)
            
            logger.info(f"Supplier {supplier.name} assigned to {updated_count} ingredients by user {user.username}")
            
            return Response({
                'success': True,
                'supplier_name': supplier.name,
                'updated_ingredients': updated_count,
                'message': f'{supplier.name} tedarikçisi {updated_count} malzemeye atandı.'
            }, status=status.HTTP_200_OK)
            
        except Supplier.DoesNotExist:
            return Response(
                {'detail': 'Belirtilen tedarikçi bulunamadı.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error assigning supplier: {str(e)}")
            return Response(
                {'detail': f'Tedarikçi ataması sırasında hata: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # +++++++++++++++++++++ YENİ ACTION +++++++++++++++++++++
    @action(detail=False, methods=['post'], url_path='send-low-stock-report')
    def send_low_stock_report(self, request):
        """
        Seçilen malzemeler için seçilen tedarikçiye manuel olarak
        düşük stok e-posta bildirimi gönderir.
        """
        user = request.user
        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_STOCK in user.staff_permissions)):
            raise PermissionDenied("Tedarikçiye bildirim gönderme yetkiniz yok.")

        supplier_id = request.data.get('supplier_id')
        ingredient_ids = request.data.get('ingredient_ids', [])

        if not supplier_id or not ingredient_ids or not isinstance(ingredient_ids, list):
            return Response(
                {'detail': 'supplier_id ve ingredient_ids (liste formatında) alanları zorunludur.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Celery görevini tetikle
        send_manual_low_stock_email_task.delay(supplier_id, ingredient_ids)
        
        logger.info(f"User {user.username} initiated manual low stock email to supplier {supplier_id} for ingredients {ingredient_ids}")
        
        return Response(
            {'detail': 'Düşük stok bildirimi e-postası başarıyla gönderim için kuyruğa alındı.'},
            status=status.HTTP_202_ACCEPTED
        )
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


class UnitOfMeasureViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [IsAuthenticated]
    queryset = UnitOfMeasure.objects.all()


class RecipeItemViewSet(viewsets.ModelViewSet):
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

        variant_id = self.request.query_params.get('variant_id')
        if variant_id:
            return queryset.filter(variant_id=variant_id)
            
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)
        variant = serializer.validated_data.get('variant')

        if not user_business or variant.menu_item.business != user_business:
            raise PermissionDenied("Bu ürüne malzeme ekleme yetkiniz yok.")
            
        serializer.save()


class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)
        if user_business:
            return Supplier.objects.filter(business=user_business)
        return Supplier.objects.none()

    def perform_create(self, serializer):
        user_business = get_user_business(self.request.user)
        serializer.save(business=user_business)

    def destroy(self, request, *args, **kwargs):
        """
        Bir tedarikçiyi silmeye çalışır. Eğer ilişkili alım siparişleri varsa,
        ProtectedError'ı yakalar ve kullanıcı dostu bir hata mesajı döndürür.
        """
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {"detail": "Bu tedarikçi, mevcut alım siparişleriyle ilişkili olduğu için silinemez. Önce ilgili siparişleri silmeniz veya düzenlemeniz gerekmektedir."},
                status=status.HTTP_400_BAD_REQUEST
            )


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)
        if user_business:
            return PurchaseOrder.objects.filter(business=user_business).prefetch_related('items__ingredient__unit').select_related('supplier')
        return PurchaseOrder.objects.none()

    # ==================== SORUN ÇÖZÜMÜ: GÜNCELLENMİŞ METOT ====================
    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)
        
        # Purchase order'ı kaydet
        purchase_order = serializer.save(business=user_business)
        
        # *** YENİ: Purchase order oluşturulduktan sonra malzemeleri güncelle ***
        try:
            items_data = self.request.data.get('items', [])
            supplier = purchase_order.supplier
            
            if supplier and items_data:
                for item_data in items_data:
                    ingredient_id = item_data.get('ingredient')
                    alert_threshold = item_data.get('alert_threshold')
                    unit_price = item_data.get('unit_price')
                    
                    if ingredient_id:
                        try:
                            ingredient = Ingredient.objects.select_for_update().get(
                                id=ingredient_id,
                                business=user_business
                            )
                            
                            updates_made = []
                            
                            # 1. Tedarikçi ataması (sadece boş ise)
                            if not ingredient.supplier:
                                ingredient.supplier = supplier
                                updates_made.append('supplier')
                            
                            # 2. Alert threshold ataması (sadece boş ise ve geçerli değer varsa)
                            if alert_threshold is not None and ingredient.alert_threshold is None:
                                try:
                                    threshold_value = Decimal(str(alert_threshold))
                                    if threshold_value > 0:
                                        ingredient.alert_threshold = threshold_value
                                        updates_made.append('alert_threshold')
                                except (ValueError, TypeError):
                                    logger.warning(f"Invalid alert_threshold value: {alert_threshold}")
                            
                            # 3. Unit cost ataması (eğer ingredient modelinde unit_cost alanı varsa)
                            if hasattr(ingredient, 'unit_cost') and unit_price is not None:
                                if ingredient.unit_cost is None or ingredient.unit_cost == 0:
                                    try:
                                        price_value = Decimal(str(unit_price))
                                        if price_value > 0:
                                            ingredient.unit_cost = price_value
                                            updates_made.append('unit_cost')
                                    except (ValueError, TypeError):
                                        logger.warning(f"Invalid unit_price value: {unit_price}")
                            
                            # Değişiklik varsa kaydet
                            if updates_made:
                                ingredient.save(update_fields=updates_made)
                                logger.info(f"✅ Purchase Order {purchase_order.id}: Ingredient {ingredient.name} updated fields: {updates_made}")
                            
                        except Ingredient.DoesNotExist:
                            logger.warning(f"❌ Purchase Order {purchase_order.id}: Ingredient ID {ingredient_id} not found")
                            continue
                        except Exception as e:
                            logger.error(f"❌ Purchase Order {purchase_order.id}: Error updating ingredient {ingredient_id}: {str(e)}")
                            continue
                
                logger.info(f"✅ Purchase Order {purchase_order.id}: Malzeme güncellemeleri tamamlandı")
        
        except Exception as e:
            logger.error(f"❌ Purchase Order {purchase_order.id}: Malzeme güncelleme sırasında genel hata: {str(e)}")
            # Hata durumunda purchase order'ı iptal etmiyoruz, sadece log yazıyoruz
    # =======================================================================
    
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_order(self, request, pk=None):
        """Beklemede olan bir alım siparişini iptal eder."""
        purchase_order = self.get_object()
        if purchase_order.status != 'pending':
            return Response(
                {'detail': 'Sadece "Beklemede" durumundaki siparişler iptal edilebilir.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        purchase_order.status = 'cancelled'
        purchase_order.save(update_fields=['status'])
        
        return Response(PurchaseOrderSerializer(purchase_order).data)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete_order(self, request, pk=None):
        purchase_order = self.get_object()
        if purchase_order.status == 'completed':
            return Response({'detail': 'Bu alım siparişi zaten tamamlanmış.'}, status=status.HTTP_400_BAD_REQUEST)
        
        purchase_order.status = 'completed'
        purchase_order.save()
        
        return Response(PurchaseOrderSerializer(purchase_order).data)