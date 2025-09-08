# core/serializers/stock_serializers.py

from rest_framework import serializers
from ..models import Stock, StockMovement, MenuItemVariant, CustomUser as User, Ingredient, UnitOfMeasure, RecipeItem, IngredientStockMovement

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
        if request and hasattr(request.user, 'business'):
            if value.menu_item.business != request.user.business:
                raise serializers.ValidationError("Seçilen varyant bu işletmeye ait değil.")
        else:
            pass
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
        if request and hasattr(request.user, 'business'):
            if value.menu_item.business != request.user.business:
                raise serializers.ValidationError("Bu varyant için stok hareketi oluşturma yetkiniz yok.")
        return value

    def create(self, validated_data):
        return super().create(validated_data)

class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = ['id', 'name', 'abbreviation']

class IngredientSerializer(serializers.ModelSerializer):
    # Okuma sırasında birim detaylarını göstermek için
    unit = UnitOfMeasureSerializer(read_only=True)
    # Yazma sırasında sadece ID almak için
    unit_id = serializers.PrimaryKeyRelatedField(
        queryset=UnitOfMeasure.objects.all(), source='unit', write_only=True
    )

    class Meta:
        model = Ingredient
        fields = [
            'id', 'name', 'unit', 'unit_id', 'stock_quantity', 
            'alert_threshold', 'last_updated', 'business'
        ]
        read_only_fields = ['last_updated', 'business']

class RecipeItemSerializer(serializers.ModelSerializer):
    """
    Bir ürün varyantının reçete kalemlerini yönetmek için serializer.
    """
    # Okuma sırasında ingredient ve unit bilgilerini detaylı göstermek için
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    unit_abbreviation = serializers.CharField(source='ingredient.unit.abbreviation', read_only=True)

    # Yazma sırasında sadece ID'leri almak için
    ingredient = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    variant = serializers.PrimaryKeyRelatedField(queryset=MenuItemVariant.objects.all())

    class Meta:
        model = RecipeItem
        fields = [
            'id',
            'variant',
            'ingredient',
            'ingredient_name',
            'unit_abbreviation',
            'quantity',
        ]
        read_only_fields = ['ingredient_name', 'unit_abbreviation']
        
class IngredientStockMovementSerializer(serializers.ModelSerializer):
    """ Malzeme stok hareketlerini serialize eder. """
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