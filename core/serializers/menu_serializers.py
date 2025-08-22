# core/serializers/menu_serializers.py

from rest_framework import serializers
from ..models import Category, MenuItem, MenuItemVariant, Stock, Business, CampaignMenu, KDSScreen 
from .kds_serializers import KDSScreenSerializer

class CategorySerializer(serializers.ModelSerializer):
    image = serializers.URLField(max_length=1024, required=False, allow_null=True)
    assigned_kds_details = KDSScreenSerializer(source='assigned_kds', read_only=True)
    assigned_kds = serializers.PrimaryKeyRelatedField(
        queryset=KDSScreen.objects.all(),
        required=False,
        allow_null=True,
        help_text="Bu kategori için atanacak KDS ekranının ID'si."
    )

    class Meta:
        model = Category
        fields = [
            'id', 'business', 'name', 'parent', 'image',
            'assigned_kds', 
            'assigned_kds_details',
            'kdv_rate'
        ]

    def validate_assigned_kds(self, value):
        if self.instance and self.instance.business and value:
            if value.business != self.instance.business:
                raise serializers.ValidationError(
                    f"Seçilen KDS ekranı ('{value.name}') bu kategorinin işletmesine ('{self.instance.business.name}') ait değil."
                )
        return value


class MenuItemVariantSerializer(serializers.ModelSerializer):
    image = serializers.URLField(max_length=1024, required=False, allow_null=True)
    menu_item_display = serializers.SerializerMethodField()

    class Meta:
        model = MenuItemVariant
        fields = ['id', 'menu_item', 'name', 'price', 'is_extra', 'image', 'menu_item_display']

    def get_menu_item_display(self, obj):
        if obj.menu_item:
            return obj.menu_item.name
        return ""


class MenuItemSerializer(serializers.ModelSerializer):
    variants = MenuItemVariantSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, required=False, allow_null=True
    )
    image = serializers.URLField(max_length=1024, required=False, allow_null=True)
    is_campaign_bundle = serializers.BooleanField(read_only=True)
    price = serializers.SerializerMethodField()
    kdv_rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)

    class Meta:
        model = MenuItem
        fields = [
            'id', 'business', 'name', 'image', 'description', 'category', 'category_id', 'variants',
            'is_campaign_bundle', 'price', 'kdv_rate',
            'is_active'  # <-- GÜNCELLEME: 'is_active' alanı eklendi
        ]
        # API üzerinden 'is_active' gönderilmese bile varsayılan olarak 'True' kabul edilmesini sağlar.
        extra_kwargs = {
            'is_active': {'required': False, 'default': True}
        }

    def get_price(self, obj: MenuItem):
        if obj.is_campaign_bundle:
            try:
                if hasattr(obj, 'represented_campaign') and obj.represented_campaign:
                    return obj.represented_campaign.campaign_price
            except CampaignMenu.DoesNotExist:
                return None
            except AttributeError:
                return None
        return None
    
    def create(self, validated_data):
        if 'kdv_rate' not in validated_data and 'category' in validated_data and validated_data['category'] is not None:
            category_instance = validated_data['category']
            validated_data['kdv_rate'] = category_instance.kdv_rate
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'kdv_rate' not in validated_data and 'category' in validated_data and validated_data['category'] is not None:
             validated_data['kdv_rate'] = validated_data['category'].kdv_rate
        
        return super().update(instance, validated_data)

    def validate_category_id(self, value):
        request = self.context.get('request')
        user_business = None
        if request and hasattr(request.user, 'user_type'):
            if request.user.user_type == 'business_owner':
                user_business = getattr(request.user, 'owned_business', None)
            elif request.user.user_type in ['staff', 'kitchen_staff']:
                user_business = getattr(request.user, 'associated_business', None)

        if value and user_business and value.business != user_business:
            raise serializers.ValidationError("Seçilen kategori bu işletmeye ait değil.")
        return value


class StockSerializer(serializers.ModelSerializer):
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    product_name = serializers.SerializerMethodField()
    variant = serializers.PrimaryKeyRelatedField(queryset=MenuItemVariant.objects.all())

    class Meta:
        model = Stock
        fields = ['id', 'variant', 'variant_name', 'product_name', 'quantity', 'last_updated', 'track_stock', 'alert_threshold']
        read_only_fields = ['last_updated']

    def get_product_name(self, obj):
        if obj.variant and obj.variant.menu_item:
            return obj.variant.menu_item.name
        return ""
    
    def validate_variant(self, value):
        request = self.context.get('request')
        user_business = None
        if request and hasattr(request.user, 'user_type'):
            if request.user.user_type == 'business_owner':
                user_business = getattr(request.user, 'owned_business', None)
            elif request.user.user_type in ['staff', 'kitchen_staff']:
                user_business = getattr(request.user, 'associated_business', None)
        
        if value and user_business:
            if value.menu_item.business != user_business:
                raise serializers.ValidationError("Seçilen varyant bu işletmeye ait değil.")
        return value