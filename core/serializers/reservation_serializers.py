# core/serializers/reservation_serializers.py

from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from ..models import Reservation, Table, Business

# İşletme sahibinin yönetim ekranı için
class ReservationSerializer(serializers.ModelSerializer):
    table_number = serializers.IntegerField(source='table.table_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Reservation
        fields = '__all__'
        read_only_fields = ('business',)

# Müşterinin web sitesinden rezervasyon yapması için
class PublicReservationCreateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Reservation
        fields = [
            'table', 'customer_name', 'customer_phone', 'customer_email',
            'reservation_time', 'party_size', 'notes'
        ]

    def validate_reservation_time(self, value):
        # Geçmişe dönük rezervasyon yapılamaz
        if value < timezone.now():
            raise serializers.ValidationError("Geçmiş bir tarih veya saate rezervasyon yapılamaz.")
        # Sadece saat başı veya yarım saatlerde rezervasyon (opsiyonel)
        if value.minute not in [0, 30]:
            raise serializers.ValidationError("Rezervasyonlar sadece saat başı veya buçuklarda yapılabilir.")
        return value

    def validate(self, data):
        table = data.get('table')
        reservation_time = data.get('reservation_time')
        
        # Seçilen masada, belirtilen saatten 1 saat öncesi ve sonrası için başka rezervasyon var mı kontrol et
        if Reservation.objects.filter(
            table=table,
            status='confirmed', # Sadece onaylanmış rezervasyonları kontrol et
            reservation_time__gte=reservation_time - timedelta(hours=1),
            reservation_time__lte=reservation_time + timedelta(hours=1)
        ).exists():
            raise serializers.ValidationError({
                "reservation_time": "Seçtiğiniz zaman dilimi bu masa için uygun değil. Lütfen başka bir saat deneyin."
            })
            
        return data