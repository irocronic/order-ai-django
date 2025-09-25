# core/serializers/waiting_customer_serializers.py

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from ..models import WaitingCustomer, Business

class WaitingCustomerSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    business = serializers.PrimaryKeyRelatedField(queryset=Business.objects.all(), required=False)

    class Meta:
        model = WaitingCustomer
        fields = ['id', 'business', 'name', 'phone', 'is_waiting', 'created_at']
        read_only_fields = ['created_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request.user, 'business') and request.user.business:
            validated_data['business'] = request.user.business
        elif 'business' not in validated_data: # Eğer request'ten gelmiyorsa ve payload'da da yoksa
             # Bu durum admin tarafından API üzerinden ekleme yapılırken business_id gönderilmezse oluşabilir.
             # Ya da işletme sahibi olmayan bir kullanıcı eklemeye çalışırsa.
            raise PermissionDenied("Bekleyen müşteri eklemek için bir işletme belirtilmeli veya işletme sahibi olmalısınız.")
        # Eğer admin ekliyorsa ve business_id payload'da geldiyse, o işletmeye eklenir.

        return super().create(validated_data)
