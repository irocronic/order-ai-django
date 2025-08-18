# core/serializers/report_serializers.py

from rest_framework import serializers

class StaffPerformanceSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField(allow_blank=True, required=False)
    last_name = serializers.CharField(allow_blank=True, required=False)
    order_count = serializers.IntegerField()
    total_turnover = serializers.DecimalField(max_digits=12, decimal_places=2)
    prepared_item_count = serializers.IntegerField(default=0)
    staff_permissions = serializers.ListField(child=serializers.CharField(), default=list)
    accessible_kds_names = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    profile_image_url = serializers.URLField(required=False, allow_null=True)


# ==================== YENİ EKLENEN BÖLÜM ====================

class DetailedSaleItemSerializer(serializers.Serializer):
    """
    Excel raporundaki her bir satış kalemini temsil eden serializer.
    Bu bir model serializer değildir, çünkü veriyi doğrudan veritabanından alıyoruz.
    """
    order_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    order_type = serializers.CharField()
    table_number = serializers.IntegerField(allow_null=True)
    customer_name = serializers.CharField(allow_null=True)
    item_name = serializers.CharField()
    variant_name = serializers.CharField(allow_null=True)
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2)

# ==================== YENİ EKLENEN BÖLÜM SONU ====================