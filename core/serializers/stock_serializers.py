# core/serializers/stock_serializers.py

from rest_framework import serializers
from ..models import Stock, StockMovement, MenuItemVariant, CustomUser as User, Ingredient, UnitOfMeasure, RecipeItem, IngredientStockMovement, Supplier, PurchaseOrder, PurchaseOrderItem
from django.db import transaction
from decimal import Decimal

class StockSerializer(serializers.ModelSerializer):
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    product_name = serializers.CharField(source='variant.menu_item.name', read_only=True)
    variant = serializers.PrimaryKeyRelatedField(queryset=MenuItemVariant.objects.all())

    class Meta:
        model = Stock
        # YENİ ALANLAR EKLENDİ: 'track_stock', 'alert_threshold'
        fields = [
            'id', 'variant', 'variant_name', 'product_name', 'quantity',
            'last_updated', 'track_stock', 'alert_threshold'
        ]
        read_only_fields = ['last_updated', 'variant_name', 'product_name']

    def validate_variant(self, value):
        request = self.context.get('request')
        user_business = None # İşletme bilgisini almak için bir helper fonksiyon daha iyi olabilir
        if request and hasattr(request.user, 'user_type'):
             if request.user.user_type == 'business_owner':
                 user_business = getattr(request.user, 'owned_business', None)
             elif request.user.user_type in ['staff', 'kitchen_staff']:
                 user_business = getattr(request.user, 'associated_business', None)

        if value and user_business and value.menu_item.business != user_business:
            raise serializers.ValidationError("Seçilen varyant bu işletmeye ait değil.")
        return value

class StockMovementSerializer(serializers.ModelSerializer):
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    product_name = serializers.CharField(source='variant.menu_item.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    variant = serializers.PrimaryKeyRelatedField(queryset=MenuItemVariant.objects.all(), write_only=True, required=False)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'stock', 'variant', 'variant_name', 'product_name',
            'movement_type', 'movement_type_display', 'quantity_change',
            'quantity_before', 'quantity_after', 'timestamp',
            'user', 'user_username', 'description', 'related_order'
        ]
        read_only_fields = [
            'stock', 'quantity_before', 'quantity_after', 'timestamp', 'user', 'user_username',
            'movement_type_display', 'variant_name', 'product_name', 'related_order'
        ]

    def validate_variant(self, value):
        request = self.context.get('request')
        user_business = None
        if request and hasattr(request.user, 'user_type'):
             if request.user.user_type == 'business_owner':
                 user_business = getattr(request.user, 'owned_business', None)
             elif request.user.user_type in ['staff', 'kitchen_staff']:
                 user_business = getattr(request.user, 'associated_business', None)
        
        if value and user_business and value.menu_item.business != user_business:
            raise serializers.ValidationError("Bu varyant için stok hareketi oluşturma yetkiniz yok.")
        return value

    def create(self, validated_data):
        return super().create(validated_data)

class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = ['id', 'name', 'abbreviation']

class IngredientSerializer(serializers.ModelSerializer):
    unit = UnitOfMeasureSerializer(read_only=True)
    unit_id = serializers.PrimaryKeyRelatedField(
        queryset=UnitOfMeasure.objects.all(), source='unit', write_only=True
    )

    class Meta:
        model = Ingredient
        fields = [
            'id', 'name', 'unit', 'unit_id', 'stock_quantity', 
            'alert_threshold', 'last_updated', 'business', 
            'supplier',
            'cost_price',
            'low_stock_notification_sent' # <<< YENİ ALAN EKLENDİ
        ]
        read_only_fields = ['last_updated', 'business']

class RecipeItemSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    unit_abbreviation = serializers.CharField(source='ingredient.unit.abbreviation', read_only=True)
    ingredient = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    variant = serializers.PrimaryKeyRelatedField(queryset=MenuItemVariant.objects.all())

    class Meta:
        model = RecipeItem
        fields = [
            'id', 'variant', 'ingredient', 'ingredient_name',
            'unit_abbreviation', 'quantity',
        ]
        read_only_fields = ['ingredient_name', 'unit_abbreviation']
        
class IngredientStockMovementSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    unit_abbreviation = serializers.CharField(source='ingredient.unit.abbreviation', read_only=True)

    class Meta:
        model = IngredientStockMovement
        fields = [
            'id', 'ingredient_name', 'unit_abbreviation', 'movement_type', 
            'movement_type_display', 'quantity_change', 'quantity_before', 
            'quantity_after', 'timestamp', 'user_username', 'description', 
            'related_order_item'
        ]

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'contact_person', 'email', 'phone', 'address']
        read_only_fields = ['business']

class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    unit_abbreviation = serializers.CharField(source='ingredient.unit.abbreviation', read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = ['id', 'ingredient', 'ingredient_name', 'unit_abbreviation', 'quantity', 'unit_price']

class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'supplier', 'supplier_name', 'status', 'order_date', 
            'notes', 'invoice_image_url', 'total_amount', 'created_at', 'updated_at', 'items'
        ]
        read_only_fields = ['business', 'created_at', 'updated_at', 'total_amount']

    @transaction.atomic
    def create(self, validated_data):
        """
        Alım Siparişi (PurchaseOrder) ve ona bağlı kalemleri (items)
        tek bir istekte oluşturmayı sağlar.
        """
        items_data = validated_data.pop('items')
        purchase_order = PurchaseOrder.objects.create(**validated_data)
        total_amount = Decimal('0.00')

        for item_data in items_data:
            PurchaseOrderItem.objects.create(purchase_order=purchase_order, **item_data)
            quantity = Decimal(str(item_data['quantity']))
            unit_price = Decimal(str(item_data['unit_price']))
            total_amount += quantity * unit_price

        purchase_order.total_amount = total_amount
        purchase_order.save()

        return purchase_order