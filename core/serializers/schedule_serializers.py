# core/serializers/schedule_serializers.py

from rest_framework import serializers
from ..models import Shift, ScheduledShift, CustomUser

class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = ['id', 'name', 'start_time', 'end_time', 'color', 'business']
        read_only_fields = ['business'] # Otomatik olarak set edilecek

class StaffForScheduleSerializer(serializers.ModelSerializer):
    """Sadece personelin adını ve ID'sini içeren basit serializer."""
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'first_name', 'last_name']


class ScheduledShiftSerializer(serializers.ModelSerializer):
    # Okuma sırasında nested bilgi göstermek için
    shift_details = ShiftSerializer(source='shift', read_only=True)
    staff_details = StaffForScheduleSerializer(source='staff', read_only=True)
    
    # Yazma sırasında sadece ID'leri almak için
    shift = serializers.PrimaryKeyRelatedField(queryset=Shift.objects.all())
    staff = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.filter(user_type__in=['staff', 'kitchen_staff']))

    class Meta:
        model = ScheduledShift
        fields = ['id', 'staff', 'staff_details', 'shift', 'shift_details', 'date']

    def validate(self, attrs):
        # Seçilen personelin ve vardiyanın aynı işletmeye ait olduğunu doğrula
        staff = attrs.get('staff')
        shift = attrs.get('shift')
        request = self.context.get('request')

        # `request` ve `request.user` varlığından emin ol
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError("İstek bağlamı eksik.")
            
        user_business = request.user.owned_business if request.user.user_type == 'business_owner' else request.user.associated_business

        if staff.associated_business != user_business:
            raise serializers.ValidationError({"staff": "Seçilen personel bu işletmeye ait değil."})
        
        if shift.business != user_business:
            raise serializers.ValidationError({"shift": "Seçilen vardiya bu işletmeye ait değil."})

        return attrs