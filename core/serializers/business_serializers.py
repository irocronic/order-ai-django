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