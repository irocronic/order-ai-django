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



class BusinessLayoutSerializer(serializers.ModelSerializer):
    """
    İşletme yerleşim planını ve üzerindeki masaları serileştirir.
    """
    tables_on_layout = TableSerializer(many=True, read_only=True)

    class Meta:
        model = BusinessLayout
        fields = ['id', 'business', 'width', 'height', 'background_image_url', 'updated_at', 'tables_on_layout']
        read_only_fields = ['business', 'updated_at', 'tables_on_layout']