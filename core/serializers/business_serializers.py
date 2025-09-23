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



Merhaba, gönderdiğiniz hata ekran görüntüsü ve sunucu logu sorunu çok net bir şekilde açıklıyor. Bu 

500 Internal Server Error hatasının, bir önceki adımda paylaştığım koddaki bir eksiklikten kaynaklandığını tespit ettim. Bu durum için özür dilerim.

Hatanın Nedeni
Hata mesajında belirtildiği gibi (

TypeError: EncryptedCharField received a non-string value), sorun Django backend'de yaşanıyor. API anahtarlarını veritabanında şifreli olarak saklamak için kullandığımız 

EncryptedCharField alanı, kendisine None (yani boş veya tanımsız) bir değer geldiğinde bu hatayı veriyor. Bu alan şifreleme yapabilmek için her zaman bir metin (string) bekler; bu metin boş bir string ('') olabilir ancak None olamaz.

Mevcut kodda, Flutter'dan anahtar alanları boş gönderildiğinde, serializer bu değeri modele None olarak aktarmaya çalışıyor ve bu da 500 sunucu hatasına neden oluyor.

Çözüm: Serializer'ı Güncellemek
Bu sorunu çözmek için Django tarafında sadece core/serializers/business_serializers.py dosyasındaki BusinessPaymentSettingsSerializer sınıfını güncellememiz yeterlidir. Yapacağımız değişiklik, None olarak gelen değerleri veritabanına kaydetmeden önce boş bir string'e ('') dönüştürmek olacak.

Aşağıda güncellenmiş ve doğru çalışan BusinessPaymentSettingsSerializer kodunu bulabilirsiniz.

Güncellenmiş Dosya: core/serializers/business_serializers.py
Lütfen bu dosyadaki mevcut BusinessPaymentSettingsSerializer sınıfını aşağıdaki kodla tamamen değiştirin.

Python

# core/serializers/business_serializers.py

# ... dosyadaki diğer serializer'lar aynı kalacak

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

    def validate(self, data):
        provider = data.get('payment_provider')
        
        # +++++++++++++++ ÇÖZÜM BURADA BAŞLIYOR +++++++++++++++
        # EncryptedCharField'ın "None" değeri kabul etmemesi sorununu çözmek için,
        # eğer anahtar değeri None ise, onu boş bir string'e ('') çeviriyoruz.
        api_key = data.get('payment_api_key', '')
        secret_key = data.get('payment_secret_key', '')

        if api_key is None:
            data['payment_api_key'] = ''
        if secret_key is None:
            data['payment_secret_key'] = ''
        # +++++++++++++++ ÇÖZÜM BURADA BİTİYOR +++++++++++++++

        # Eğer bir sağlayıcı seçildiyse (Entegrasyon Yok dışında), anahtarların girildiğinden emin ol.
        if provider and provider != Business.PaymentProvider.NONE:
            # Kontrolü güncellenmiş (None'dan string'e çevrilmiş) değerler üzerinden yapıyoruz.
            if not data.get('payment_api_key') or not data.get('payment_secret_key'):
                raise serializers.ValidationError(
                    "Seçilen ödeme sağlayıcısı için API Anahtarı ve Gizli Anahtar alanları zorunludur."
                )
        return data