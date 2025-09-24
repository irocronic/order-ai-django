# core/serializers/business_serializers.py

from rest_framework import serializers
from ..models import Business, Table, BusinessLayout, LayoutElement

class BusinessSerializer(serializers.ModelSerializer):
    """
    İşletme modelinin detaylarını serileştirmek için kullanılır.
    """
    class Meta:
        model = Business
        # === GÜNCELLEME BURADA: 'timezone' alanı fields listesine eklendi ===
        fields = ['id', 'owner', 'name', 'address', 'phone', 'is_setup_complete', 'currency_code', 'timezone']


class TableSerializer(serializers.ModelSerializer):
    """
    Masa modelini serileştirmek için kullanılır. Konum bilgileri eklendi.
    """
    class Meta:
        model = Table
        fields = ['id', 'table_number', 'uuid', 'business', 'layout', 'pos_x', 'pos_y', 'rotation']
        read_only_fields = ['uuid', 'business'] # layout ve business genellikle otomatik atanır






# === YENİ SERIALIZER BAŞLANGICI ===
class LayoutElementSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayoutElement
        fields = [
            'id', 'layout', 'element_type', 'pos_x', 'pos_y',
            'width', 'height', 'rotation', 'style_properties'
        ]
        read_only_fields = ['layout']
# === YENİ SERIALIZER SONU ===





# === DEĞİŞİKLİK BURADA BAŞLIYOR ===

class BusinessLayoutSerializer(serializers.ModelSerializer):
    """
    İşletme yerleşim planını, üzerindeki masaları ve dekoratif öğeleri serileştirir.
    """
    tables_on_layout = serializers.SerializerMethodField()
    # === YENİ ALAN EKLENDİ ===
    elements = LayoutElementSerializer(many=True, read_only=True)

    class Meta:
        model = BusinessLayout
        # === 'elements' ALANI LİSTEYE EKLENDİ ===
        fields = ['id', 'business', 'width', 'height', 'background_image_url', 'updated_at', 'tables_on_layout', 'elements']
        read_only_fields = ['business', 'updated_at']

    def get_tables_on_layout(self, obj: BusinessLayout):
        """
        Bu metot, yerleşim planının ait olduğu işletmedeki TÜM masaları çeker.
        Bu sayede, henüz bir konuma atanmamış masalar da planlayıcıda görünür olur.
        """
        # obj, o anki BusinessLayout nesnesidir.
        all_business_tables = Table.objects.filter(business=obj.business)
        serializer = TableSerializer(all_business_tables, many=True)
        return serializer.data

# === DEĞİŞİKLİK BURADA BİTİYOR ===



class BusinessPaymentSettingsSerializer(serializers.ModelSerializer):
    """
    İşletmenin ödeme sağlayıcı ayarlarını güncellemek için kullanılır.
    API anahtarları sadece yazma amaçlıdır, okuma sırasında asla gönderilmez.
    """
    class Meta:
        model = Business
        fields = [
            'payment_provider',
            'payment_api_key',
            'payment_secret_key'
        ]
        extra_kwargs = {
            'payment_api_key': {'write_only': True, 'required': False, 'allow_blank': True, 'allow_null': True},
            'payment_secret_key': {'write_only': True, 'required': False, 'allow_blank': True, 'allow_null': True},
        }

    def to_internal_value(self, data):
        """
        DÜZELTME: Daha basit ve güvenilir yaklaşım
        Gelen veriyi aynen işle, boş string'leri koru
        """
        ret = super().to_internal_value(data)
        
        # Sadece provider değişikliği kontrolü
        if 'payment_provider' in data:
            ret['payment_provider'] = data['payment_provider']
            
        # API key varsa işle
        if 'payment_api_key' in data:
            ret['payment_api_key'] = data['payment_api_key'] or ''
            
        # Secret key varsa işle    
        if 'payment_secret_key' in data:
            ret['payment_secret_key'] = data['payment_secret_key'] or ''
            
        return ret
    
    def validate(self, data):
        """
        DÜZELTME: Validasyon mantığı düzeltildi
        """
        # Provider bilgisini al
        provider = data.get('payment_provider')
        if provider is None and self.instance:
            provider = self.instance.payment_provider

        # Eğer provider 'none' değilse, anahtarların dolu olması gerekir
        if provider and provider != Business.PaymentProvider.NONE:
            # API key kontrolü
            api_key = data.get('payment_api_key')
            if api_key is None and self.instance:
                api_key = self.instance.payment_api_key
                
            # Secret key kontrolü
            secret_key = data.get('payment_secret_key')
            if secret_key is None and self.instance:
                secret_key = self.instance.payment_secret_key
                
            # Boş kontrolü
            if not api_key or not api_key.strip():
                raise serializers.ValidationError(
                    "Seçilen ödeme sağlayıcısı için API Anahtarı zorunludur."
                )
            if not secret_key or not secret_key.strip():
                raise serializers.ValidationError(
                    "Seçilen ödeme sağlayıcısı için Gizli Anahtar zorunludur."
                )
        
        return data

    def update(self, instance, validated_data):
        """
        DÜZELTME: Güncelleme işlemi için özel save mantığı
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Serializer update çağrıldı - Instance ID: {instance.id}")
        
        # Alanları güncelle
        for attr, value in validated_data.items():
            logger.info(f"Güncelleniyor - {attr}: {bool(value) if 'key' in attr else value}")
            setattr(instance, attr, value)
        
        # Kaydet
        instance.save()
        
        # Refresh from DB to ensure we have latest data
        instance.refresh_from_db()
        
        logger.info(f"Update tamamlandı - API Key dolu: {bool(instance.payment_api_key)}")
        logger.info(f"Update tamamlandı - Secret Key dolu: {bool(instance.payment_secret_key)}")
        
        return instance