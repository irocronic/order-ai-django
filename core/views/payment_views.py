# core/views/payment_views.py

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from ..models import Payment, Business, Order # Business ve Order import edildi
from ..serializers import PaymentSerializer
from .order_views import get_user_business # order_views.py'deki helper fonksiyonu import ediyoruz

class PaymentViewSet(viewsets.ModelViewSet):
    """
    Ödeme işlemlerini doğrudan yönetir.
    Genellikle sipariş üzerinden ödeme alınır (OrderViewSet.mark_as_paid),
    ancak bu ViewSet doğrudan Payment objeleri üzerinde işlem yapmak için de kullanılabilir.
    """
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    # queryset = Payment.objects.all() # get_queryset ile filtrelenecek (Kaldırıldı)

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user) # Helper fonksiyonu kullan

        if not user_business:
            # if user.is_staff or user.is_superuser: # Admin tüm ödemeleri görebilir (opsiyonel)
            #     return Payment.objects.all().select_related('order__business')
            return Payment.objects.none()
        
        return Payment.objects.filter(order__business=user_business).select_related('order__business')

    def perform_create(self, serializer):
        user = self.request.user
        order_instance = serializer.validated_data.get('order')
        
        if not order_instance:
            raise PermissionDenied("Ödeme için bir sipariş belirtilmelidir.")

        user_business = get_user_business(user) # Helper fonksiyonu kullan
        
        if not user_business:
            raise PermissionDenied("Ödeme oluşturmak için yetkili bir işletmeniz bulunmuyor.")

        # Ödeme yapılan siparişin, işlemi yapan kullanıcının işletmesine ait olup olmadığını kontrol et
        if order_instance.business != user_business:
            # Adminler için bir istisna eklenebilir (eğer farklı işletmelerin siparişlerine ödeme ekleyebilmeleri gerekiyorsa)
            if not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Bu sipariş sizin işletmenize ait değil, ödeme alamazsınız.")
        
        # PaymentSerializer'ın create metodu zaten order.is_paid = True yapıyor.
        # Ayrıca order.taken_by_staff gibi alanlar Payment oluşturulurken değil, Order oluşturulurken setlenir.
        serializer.save() # order zaten validated_data içinde olduğu için tekrar göndermeye gerek yok.
                         # Serializer'ın create metodu order'ı ve diğer alanları kullanır.
    
    # perform_update ve perform_destroy için de benzer yetki kontrolleri eklenebilir,
    # ancak ödemeler genellikle güncellenmez veya silinmez; ya iptal edilir ya da iade işlemi yapılır.
    # Bu ViewSet'i sadece listeleme ve oluşturma (nadiren) için kullanmak daha yaygındır.
    def perform_update(self, serializer):
        user = self.request.user
        payment_instance = serializer.instance
        user_business = get_user_business(user)

        if not user_business or payment_instance.order.business != user_business:
            if not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Bu ödemeyi güncelleme yetkiniz yok.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business or instance.order.business != user_business:
             if not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Bu ödemeyi silme yetkiniz yok.")
        # Genellikle ödemeler silinmez, ancak bu örnekte bırakıyorum.
        instance.delete()