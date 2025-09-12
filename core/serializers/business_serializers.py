# core/serializers/business_serializers.py

from rest_framework import serializers
from ..models import Business, Table

class BusinessSerializer(serializers.ModelSerializer):
    """
    İşletme modelinin detaylarını serileştirmek için kullanılır.
    """
    class Meta:
        model = Business
        # === GÜNCELLEME BURADA: Yeni web sitesi alanları fields listesine eklendi ===
        fields = [
            'id', 'owner', 'name', 'address', 'phone', 'is_setup_complete', 
            'currency_code', 'timezone',
            'website_slug', 'about_us', 'contact_details'  # <-- YENİ ALANLAR
        ]
        read_only_fields = ['owner']  # Slug'ı kullanıcı değiştirebilsin diye read_only'den çıkarıyoruz


class TableSerializer(serializers.ModelSerializer):
    """
    Masa modelini serileştirmek için kullanılır.
    """
    class Meta:
        model = Table
        fields = ['id', 'table_number', 'uuid', 'business']