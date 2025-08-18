# core/serializers/campaign_serializers.py

from rest_framework import serializers
from decimal import Decimal
from ..models import CampaignMenu, CampaignMenuItem, MenuItem, MenuItemVariant, Business

class CampaignMenuItemSerializer(serializers.ModelSerializer):
    # Okuma sırasında ürün ve varyant adlarını göstermek için
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True, allow_null=True)
    original_price = serializers.SerializerMethodField()

    class Meta:
        model = CampaignMenuItem
        fields = ['id', 'menu_item', 'menu_item_name', 'variant', 'variant_name', 'quantity', 'original_price']
        # 'campaign_menu' alanı create/update sırasında parent serializer tarafından sağlanacak.

    def get_original_price(self, obj: CampaignMenuItem) -> Decimal:
        if obj.variant:
            return obj.variant.price
        elif obj.menu_item: # Eğer ana ürünün varyantsız bir temel fiyatı varsa
            # MenuItem modelinde base_price gibi bir alan varsa o kullanılabilir.
            # Şimdilik MenuItem'in direkt fiyatı olmadığını varsayarak,
            # eğer varyant yoksa ve MenuItem'in tek bir normal varyantı varsa onun fiyatını alalım.
            default_variant = obj.menu_item.variants.filter(is_extra=False).first()
            if default_variant:
                return default_variant.price
        return Decimal('0.00')

    def validate_menu_item(self, value):
        # Kampanyaya eklenecek menü öğesinin kampanya paketi olmamasını sağla
        if value.is_campaign_bundle:
            raise serializers.ValidationError("Bir kampanya paketine başka bir kampanya paketi eklenemez.")
        return value

    def validate(self, data):
        menu_item = data.get('menu_item')
        variant = data.get('variant')
        if menu_item:
            # Eğer varyant seçilmişse, bu varyantın ana ürüne ait olup olmadığını kontrol et
            if variant and variant.menu_item != menu_item:
                raise serializers.ValidationError(
                    f"'{variant.name}' adlı varyant, '{menu_item.name}' ürününe ait değil."
                )
            # Eğer ana ürünün normal varyantları varsa ama hiçbiri seçilmemişse hata ver
            elif not variant and menu_item.variants.filter(is_extra=False).exists():
                raise serializers.ValidationError(
                    f"'{menu_item.name}' ürünü için bir varyant seçilmelidir."
                )
        return data


class CampaignMenuSerializer(serializers.ModelSerializer):
    campaign_items = CampaignMenuItemSerializer(many=True, help_text="Kampanyaya dahil edilecek ürünler ve miktarları.")
    business_name = serializers.CharField(source='business.name', read_only=True)
    total_normal_price = serializers.SerializerMethodField()
    bundle_menu_item_id = serializers.IntegerField(source='bundle_menu_item.id', read_only=True, allow_null=True)

    class Meta:
        model = CampaignMenu
        fields = [
            'id', 'business', 'business_name', 'name', 'description', 'image',
            'campaign_price', 'total_normal_price', 'campaign_items',
            'is_active', 'start_date', 'end_date', 'created_at', 'updated_at',
            'bundle_menu_item_id'
        ]
        read_only_fields = ('business', 'created_at', 'updated_at', 'total_normal_price', 'bundle_menu_item_id')
        # 'business' alanı perform_create'de otomatik atanacak.

    def get_total_normal_price(self, obj: CampaignMenu) -> Decimal:
        total = Decimal('0.00')
        for item in obj.campaign_items.all():
            price = Decimal('0.00')
            if item.variant:
                price = item.variant.price
            elif item.menu_item: # Varyantsız ana ürün (eğer varsa)
                default_variant = item.menu_item.variants.filter(is_extra=False).first()
                if default_variant:
                    price = default_variant.price
            total += price * item.quantity
        return total

    def validate_campaign_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Kampanya fiyatı pozitif bir değer olmalıdır.")
        return value

    def validate_campaign_items(self, items_data):
        if not items_data:
            raise serializers.ValidationError("Kampanya en az bir ürün içermelidir.")
        # Aynı ürün/varyant kombinasyonunun birden fazla kez eklenmediğini kontrol et (unique_together zaten modelde var)
        seen_items = set()
        for item in items_data:
            item_key = (item['menu_item'].id, item.get('variant').id if item.get('variant') else None)
            if item_key in seen_items:
                raise serializers.ValidationError(f"'{item['menu_item'].name}' ürünü/varyantı kampanyaya birden fazla kez eklenemez.")
            seen_items.add(item_key)
        return items_data

    def create(self, validated_data):
        items_data = validated_data.pop('campaign_items')
        campaign = CampaignMenu.objects.create(**validated_data)
        for item_data in items_data:
            CampaignMenuItem.objects.create(campaign_menu=campaign, **item_data)
        # İlgili MenuItem'ı oluşturma veya güncelleme işlemi ViewSet'te veya sinyalde yapılabilir.
        return campaign

    def update(self, instance, validated_data):
        items_data = validated_data.pop('campaign_items', None)
        instance = super().update(instance, validated_data)

        if items_data is not None:
            instance.campaign_items.all().delete() # Önceki tüm kalemleri sil
            for item_data in items_data:
                CampaignMenuItem.objects.create(campaign_menu=instance, **item_data)
        # İlgili MenuItem'ı oluşturma veya güncelleme işlemi ViewSet'te veya sinyalde yapılabilir.
        return instance