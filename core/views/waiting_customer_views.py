# core/views/waiting_customer_views.py

from rest_framework import generics, status # status eklendi
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError # ValidationError eklendi
from django.utils import timezone # Opsiyonel: called_at, seated_at için
import logging

# Socket.IO için importlar
from asgiref.sync import async_to_sync
from makarna_project.asgi import sio # asgi.py dosyanızdaki sio instance'ı

from ..models import WaitingCustomer, Business, CustomUser as User
from ..serializers import WaitingCustomerSerializer # WaitingCustomerSerializer'ı import ettiğinizden emin olun

# get_user_business helper fonksiyonunu ve PermissionKeys'i import edelim
# Bu fonksiyonu ve sınıfı bir utils.py veya permissions.py dosyasında merkezi olarak tanımlamanız en iyisidir
# Şimdilik, daha önceki view dosyalarındaki gibi burada da tanımlayabiliriz veya import edebiliriz.
# Bu örnekte, order_views.py'den import edildiğini varsayıyorum.
from .order_views import get_user_business, PermissionKeys # Veya kendi tanımladığınız yer


logger = logging.getLogger(__name__)

class WaitingCustomerList(generics.ListCreateAPIView):
    serializer_class = WaitingCustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business:
            # if user.is_staff or user.is_superuser: # Admin tümünü görebilir (opsiyonel)
            #     return WaitingCustomer.objects.filter(is_waiting=True).order_by('created_at')
            return WaitingCustomer.objects.none()

        if user.user_type == 'staff' and PermissionKeys.MANAGE_WAITING_CUSTOMERS not in user.staff_permissions:
            return WaitingCustomer.objects.none()
            
        return WaitingCustomer.objects.filter(
            business=user_business, 
            # is_waiting=True # Listelemede sadece bekleyenleri değil, tümünü (veya parametreye göre) getirebiliriz
        ).order_by('-is_waiting', 'created_at') # Önce bekleyenler, sonra oluşturulma tarihine göre

    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)

        if not user_business:
            raise PermissionDenied("Bekleyen müşteri eklemek için yetkili bir işletmeniz bulunmuyor.")

        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_WAITING_CUSTOMERS in user.staff_permissions)):
            raise PermissionDenied("Bekleyen müşteri ekleme yetkiniz yok.")
        
        # party_size ve notes alanlarını request.data'dan al
        party_size = self.request.data.get('party_size', 1)
        notes = self.request.data.get('notes', None)

        try:
            party_size = int(party_size)
            if party_size <= 0:
                raise ValueError()
        except ValueError:
            raise ValidationError({"party_size": "Geçerli bir kişi sayısı girin."})

        waiting_customer = serializer.save(
            business=user_business,
            party_size=party_size,
            notes=notes,
            is_waiting=True # Yeni eklenen müşteri her zaman bekliyor olmalı
        )
        logger.info(f"Waiting customer {waiting_customer.name} (ID: {waiting_customer.id}) created for business {user_business.name} by {user.username}")

        # Socket.IO bildirimi gönder
        if sio:
            room_name = f'business_{user_business.id}'
            payload = {
                'event_type': 'waiting_customer_added',
                'message': f"Yeni bekleyen müşteri eklendi: {waiting_customer.name}",
                'business_id': user_business.id,
                'customer_data': WaitingCustomerSerializer(waiting_customer).data # Yeni müşteri verisini gönder
            }
            try:
                async_to_sync(sio.emit)('waiting_list_update', payload, room=room_name)
                logger.info(f"Socket.IO 'waiting_list_update' (added) sent for customer {waiting_customer.id}")
            except Exception as e:
                logger.error(f"Socket.IO error sending waiting_customer_added event: {e}", exc_info=True)


class WaitingCustomerDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WaitingCustomerSerializer
    permission_classes = [IsAuthenticated]
    queryset = WaitingCustomer.objects.all() # get_object içinde filtrelenecek

    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        user_business = get_user_business(user)
        can_access = False

        if user_business and obj.business == user_business:
            if user.user_type == 'business_owner' or \
               (user.user_type == 'staff' and PermissionKeys.MANAGE_WAITING_CUSTOMERS in user.staff_permissions):
                can_access = True
        
        # Adminler için özel durum (opsiyonel)
        # elif user.is_staff or user.is_superuser:
        #    can_access = True
            
        if not can_access:
            raise PermissionDenied("Bu bekleyen müşteri kaydına erişim yetkiniz yok.")
        return obj

    def perform_update(self, serializer):
        user = self.request.user
        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_WAITING_CUSTOMERS in user.staff_permissions)):
            raise PermissionDenied("Bekleyen müşteri güncelleme yetkiniz yok.")

        instance_before_update = self.get_object() # Güncellemeden önceki hali al
        old_is_waiting = instance_before_update.is_waiting
        
        # called_at ve seated_at alanlarını is_waiting durumuna göre ayarla
        current_is_waiting = serializer.validated_data.get('is_waiting', instance_before_update.is_waiting)
        
        update_fields = [] # Sadece değişen alanları kaydetmek için
        
        # Eğer is_waiting False yapılıyorsa ve seated_at henüz ayarlanmamışsa, şimdi ayarla
        if not current_is_waiting and instance_before_update.is_waiting and instance_before_update.seated_at is None:
            serializer.validated_data['seated_at'] = timezone.now()
            update_fields.append('seated_at')
        
        # Django REST framework, partial update (PATCH) için instance'ı güncellerken
        # serializer.save() zaten sadece gönderilen alanları günceller.
        # Ancak `is_waiting` gibi alanların `save` öncesinde `validated_data` içinde olduğundan emin olmalıyız.
        # Ya da `serializer.save(is_waiting=current_is_waiting)` gibi direkt parametre geçebiliriz.

        updated_customer = serializer.save() # Güncellemeyi yap
        new_is_waiting = updated_customer.is_waiting
        
        logger.info(f"Waiting customer {updated_customer.name} (ID: {updated_customer.id}) updated by {user.username}")

        # Socket.IO bildirimi gönder (durum değiştiyse veya her zaman)
        # if old_is_waiting != new_is_waiting: # Sadece is_waiting değiştiyse gönder
        if sio:
            room_name = f'business_{updated_customer.business.id}'
            payload = {
                'event_type': 'waiting_customer_updated',
                'message': f"Bekleyen müşteri durumu güncellendi: {updated_customer.name}",
                'business_id': updated_customer.business.id,
                'customer_data': WaitingCustomerSerializer(updated_customer).data # Güncellenmiş müşteri verisini gönder
            }
            try:
                async_to_sync(sio.emit)('waiting_list_update', payload, room=room_name)
                logger.info(f"Socket.IO 'waiting_list_update' (updated) sent for customer {updated_customer.id}")
            except Exception as e:
                logger.error(f"Socket.IO error sending waiting_customer_updated event: {e}", exc_info=True)

    def perform_destroy(self, instance: WaitingCustomer): # Tip WaitingCustomer olarak belirtildi
        user = self.request.user
        if not (user.user_type == 'business_owner' or 
                (user.user_type == 'staff' and PermissionKeys.MANAGE_WAITING_CUSTOMERS in user.staff_permissions)):
            raise PermissionDenied("Bekleyen müşteri silme yetkiniz yok.")

        business_id = instance.business.id
        customer_id = instance.id
        customer_name = instance.name

        instance.delete()
        logger.info(f"Waiting customer {customer_name} (ID: {customer_id}) deleted by {user.username}")

        # Socket.IO bildirimi gönder
        if sio:
            room_name = f'business_{business_id}'
            payload = {
                'event_type': 'waiting_customer_removed',
                'message': f"Bekleyen müşteri silindi: {customer_name} (ID: {customer_id})",
                'business_id': business_id,
                'customer_id': customer_id, # Silinen müşterinin ID'sini gönder
            }
            try:
                async_to_sync(sio.emit)('waiting_list_update', payload, room=room_name)
                logger.info(f"Socket.IO 'waiting_list_update' (removed) sent for customer {customer_id}")
            except Exception as e:
                logger.error(f"Socket.IO error sending waiting_customer_removed event: {e}", exc_info=True)