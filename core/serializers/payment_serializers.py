# core/serializers/payment_serializers.py

from rest_framework import serializers
from ..models import Payment, CreditPaymentDetails, Order

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order', 'payment_type', 'amount', 'payment_date']
        read_only_fields = ['payment_date']

class CreditPaymentDetailsSerializer(serializers.ModelSerializer):
    # Bu serializer sadece CreditPaymentDetails modeline ait alanları içermelidir.
    # Müşteri adı, telefonu gibi Order modeline ait bilgiler,
    # OrderSerializer tarafından zaten sağlanmaktadır.

    # Eğer order ID yerine daha fazla bilgi (örn: order'ın __str__ metodu) isteniyorsa:
    # order_display = serializers.StringRelatedField(source='order', read_only=True)

    class Meta:
        model = CreditPaymentDetails
        fields = [
            'id', 
            'order', # Bu, Order modelinin ID'sini döndürecektir.
            # 'order_display', # Eğer StringRelatedField kullanırsanız
            'notes', 
            'created_at', 
            'paid_at'
        ]
        # 'order' alanı genellikle oluşturma sırasında set edilir veya read_only olabilir.
        # Modelde OneToOneField olduğu için, Order oluşturulduktan sonra CreditPaymentDetails oluşturulur.
        read_only_fields = ['created_at', 'paid_at', 'order']