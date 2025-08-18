# core/serializers/pager_serializers.py

from rest_framework import serializers
from ..models import Pager, Order, Business # Business modelini de import edelim

class PagerOrderSerializer(serializers.ModelSerializer):
    """ Pager listesinde sipariş detayını göstermek için basit serializer """
    table_number_display = serializers.SerializerMethodField()
    customer_name_display = serializers.SerializerMethodField()

    class Meta:
        model = Order
        # Siparişten göstermek istediğiniz temel alanlar
        fields = ['id', 'order_type', 'table_number_display', 'customer_name_display', 'status_display']

    def get_table_number_display(self, obj: Order) -> str | None: # Tip ipucu eklendi
        return obj.table.table_number if obj.table else None

    def get_customer_name_display(self, obj: Order) -> str | None: # Tip ipucu eklendi
        return obj.customer_name or (obj.customer.username if obj.customer else None)
    
    # status_display Order modelinde get_status_display() ile geliyor, direkt source edebiliriz
    # veya OrderSerializer gibi bir yerden bu mantığı alabiliriz.
    # Şimdilik, Order modelinin get_status_display() metodunu kullandığını varsayalım.
    status_display = serializers.CharField(source='get_status_display', read_only=True)


class PagerSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    # current_order alanı ID olarak dönecek, current_order_details ise daha fazla bilgiyle.
    current_order_details = PagerOrderSerializer(source='current_order', read_only=True)
    
    # Business alanı oluşturma ve güncelleme sırasında ID olarak alınacak.
    business = serializers.PrimaryKeyRelatedField(queryset=Business.objects.all())

    class Meta:
        model = Pager
        fields = [
            'id', 'business', 'business_name', 'device_id', 'name',
            'status', 'status_display', 'current_order', 'current_order_details',
            'last_status_update', 'notes'
        ]
        read_only_fields = ['last_status_update', 'business_name', 'status_display', 'current_order_details']
        extra_kwargs = {
            'current_order': {'required': False, 'allow_null': True}, # API üzerinden direkt order ataması için
            'name': {'required': False, 'allow_null': True, 'allow_blank': True},
            'notes': {'required': False, 'allow_null': True, 'allow_blank': True},
        }

    def validate_device_id(self, value):
        request_user = self.context['request'].user
        # 'business' alanı create sırasında doğrudan payload'dan veya perform_create'den gelebilir.
        # Eğer instance varsa, instance.business kullanılır.
        business_instance = self.initial_data.get('business') # Create için
        if self.instance: # Update için
            business_instance = self.instance.business
        
        # Eğer business_instance bir ID ise, objeye çevir
        if isinstance(business_instance, int):
            try:
                business_instance = Business.objects.get(pk=business_instance)
            except Business.DoesNotExist:
                raise serializers.ValidationError("Belirtilen işletme bulunamadı.")

        if not business_instance and request_user.user_type == 'business_owner':
             business_instance = request_user.owned_business
        elif not business_instance and request_user.user_type == 'staff':
            business_instance = request_user.associated_business


        if not business_instance:
             # Admin için veya business belirtilmemişse genel kontrol (pek olası değil)
            query = Pager.objects.filter(device_id=value)
            if self.instance:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                 raise serializers.ValidationError("Bu cihaz ID'si sistemde zaten başka bir işletme için kayıtlı.")
            return value

        # Belirli bir işletme için device_id benzersizliği kontrolü
        query = Pager.objects.filter(business=business_instance, device_id=value)
        if self.instance: # Güncelleme ise kendi ID'sini hariç tut
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("Bu cihaz ID'si zaten bu işletmede kayıtlı.")
        return value

    def validate(self, data):
        # Eğer status 'in_use' ise current_order zorunlu olmalı
        # Update durumunda instance üzerinden eski status'u alabiliriz.
        status_val = data.get('status', self.instance.status if self.instance else None)
        current_order_val = data.get('current_order', self.instance.current_order if self.instance else None)

        if status_val == 'in_use' and current_order_val is None:
            # Eğer yeni bir Pager oluşturuluyorsa ve status='in_use' ise current_order zorunlu
            if not self.instance: # Create işlemi
                 raise serializers.ValidationError({"current_order": "'Kullanımda' durumundaki çağrı cihazı bir siparişe atanmalıdır."})
            # Update işleminde, eğer status 'in_use' yapılıyorsa ve current_order boşsa, hata ver.
            # Bu durum genellikle OrderSerializer tarafından yönetilir (pager'a order atanırken).
            # Bu serializer daha çok pager'ın kendi bilgilerini ve durumunu güncellemek için.
        elif status_val != 'in_use' and current_order_val is not None:
            # Eğer cihaz 'boşta' veya başka bir durumda ise, current_order null olmalı.
            # Bu, API üzerinden yanlış atamaları engeller. Sinyaller de bunu yönetir.
            # Ancak, bir pager'ı 'in_use' durumundan başka bir duruma alırken,
            # current_order'ı otomatik olarak null yapmak PagerViewSet'in sorumluluğunda olabilir.
            # Serializer'da bu validasyon, isteğin current_order ile birlikte gelmemesini sağlar.
             if self.instance and self.instance.current_order != current_order_val: # Eğer current_order da değiştirilmiyorsa
                pass # PagerViewSet veya sinyal bu durumu ele alacak
             elif not self.instance: # Create işlemi için
                data['current_order'] = None


        # Eğer bir order atanıyorsa, o order'ın başka bir pager'a atanmamış olduğundan emin ol.
        if current_order_val:
            other_pager_with_this_order = Pager.objects.filter(current_order=current_order_val).exclude(pk=self.instance.pk if self.instance else None)
            if other_pager_with_this_order.exists():
                raise serializers.ValidationError({"current_order": f"Bu sipariş (#{current_order_val.id}) zaten başka bir çağrı cihazına ({other_pager_with_this_order.first()}) atanmış."})

        return data