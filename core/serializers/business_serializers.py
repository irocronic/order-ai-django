# core/serializers/business_serializers.py

from rest_framework import serializers
from ..models import Business, Table, BusinessLayout

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


# === DEĞİŞİKLİK BURADA BAŞLIYOR ===

class BusinessLayoutSerializer(serializers.ModelSerializer):
    """
    İşletme yerleşim planını ve üzerindeki masaları serileştirir.
    Artık işletmeye ait TÜM masaları getirecek şekilde güncellendi.
    """
    # Mevcut 'tables_on_layout' alanını, tüm masaları getirecek özel bir metotla değiştiriyoruz.
    # Flutter tarafında değişiklik yapmamak için alan adını aynı tutuyoruz.
    tables_on_layout = serializers.SerializerMethodField()

    class Meta:
        model = BusinessLayout
        fields = ['id', 'business', 'width', 'height', 'background_image_url', 'updated_at', 'tables_on_layout']
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