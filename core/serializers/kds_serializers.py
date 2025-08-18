# core/serializers/kds_serializers.py
from rest_framework import serializers
from ..models import KDSScreen, Business

class KDSScreenSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    # business alanı create/update için PrimaryKeyRelatedField olarak alınır,
    # view'da perform_create/perform_update içinde otomatik set edilebilir.
    business = serializers.PrimaryKeyRelatedField(queryset=Business.objects.all(), write_only=True)

    class Meta:
        model = KDSScreen
        fields = [
            'id', 'business', 'business_name', 'name', 'slug',
            'description', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ('slug', 'created_at', 'updated_at', 'business_name')

    def validate_name(self, value):
        # Aynı işletme içinde aynı isimde KDS olmamasını sağla (unique_together zaten modelde var ama serializer seviyesinde de iyi)
        request = self.context.get('request')
        business_instance = None

        # Güncelleme durumu
        if self.instance:
            business_instance = self.instance.business
        # Oluşturma durumu (eğer business payload'da ID olarak geliyorsa)
        elif 'business' in self.initial_data:
            try:
                business_pk = self.initial_data['business']
                business_instance = Business.objects.get(pk=business_pk)
            except Business.DoesNotExist:
                raise serializers.ValidationError("Belirtilen işletme bulunamadı.")
        # Oluşturma durumu (eğer view perform_create içinde set edecekse)
        elif request and hasattr(request.user, 'owned_business') and request.user.user_type == 'business_owner':
             business_instance = request.user.owned_business
        elif request and hasattr(request.user, 'associated_business') and request.user.user_type == 'staff':
             business_instance = request.user.associated_business


        if business_instance:
            query = KDSScreen.objects.filter(business=business_instance, name=value)
            if self.instance: # Güncelleme ise kendi ID'sini hariç tut
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise serializers.ValidationError("Bu KDS ekran adı zaten bu işletmede kullanılıyor.")
        else:
            # Business olmadan bu validasyon tam yapılamaz. ViewSet'te kontrol edilmeli.
            pass
        return value