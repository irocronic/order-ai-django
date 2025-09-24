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

    def __init__(self, *args, **kwargs):
        # PUT metodu kullanıldığında partial=False olmasına rağmen,
        # anahtar alanları zorunlu olmadığı için eksik olabilirler.
        # Bu yüzden partial=True'yu zorunlu kılarak sadece gönderilen alanların
        # güncellenmesini sağlıyoruz. Bu, PUT ve PATCH davranışını birleştirir.
        kwargs['partial'] = True
        super(BusinessPaymentSettingsSerializer, self).__init__(*args, **kwargs)

    def to_internal_value(self, data):
        # Bu metot, validate'den önce çalışir ve gelen veriyi Python tiplerine çevirir.
        ret = super().to_internal_value(data)
        
        # DÜZELTME: Sadece gelen data'da varsa işleme al, yoksa mevcut değeri koru
        if 'payment_api_key' in data:
            if data.get('payment_api_key') is None or data.get('payment_api_key') == '':
                ret['payment_api_key'] = ''
            else:
                ret['payment_api_key'] = data['payment_api_key']
                
        if 'payment_secret_key' in data:
            if data.get('payment_secret_key') is None or data.get('payment_secret_key') == '':
                ret['payment_secret_key'] = ''
            else:
                ret['payment_secret_key'] = data['payment_secret_key']
            
        return ret
    
    def validate(self, data):
        # Mevcut instance'dan değerleri al
        provider = data.get('payment_provider', self.instance.payment_provider if self.instance else None)
        
        # API key için: gelen data'da varsa onu al, yoksa mevcut değeri kullan
        api_key = data.get('payment_api_key')
        if api_key is None and self.instance:
            api_key = self.instance.payment_api_key
            
        # Secret key için: gelen data'da varsa onu al, yoksa mevcut değeri kullan    
        secret_key = data.get('payment_secret_key')
        if secret_key is None and self.instance:
            secret_key = self.instance.payment_secret_key

        # Eğer bir sağlayıcı seçildiyse (Entegrasyon Yok dışında), anahtarların girildiğinden emin ol.
        if provider and provider != Business.PaymentProvider.NONE:
            if not api_key or not secret_key:
                raise serializers.ValidationError(
                    "Seçilen ödeme sağlayıcısı için API Anahtarı ve Gizli Anahtar alanları zorunludur."
                )
        return data