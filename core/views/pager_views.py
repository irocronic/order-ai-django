# core/views/pager_views.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404 # Kullanılmıyorsa kaldırılabilir, ViewSet kendi get_object'ini kullanır.
from rest_framework.exceptions import PermissionDenied, ValidationError # ValidationError eklendi
import logging

from ..models import Pager, Order, Business, CustomUser
from ..serializers import PagerSerializer
from ..utils.order_helpers import get_user_business
# STAFF_PERMISSION_CHOICES ve 'manage_pagers' anahtarının burada doğrudan kullanılmasına gerek yok,
# kontrol CustomUser.staff_permissions içinde yapılır.

logger = logging.getLogger(__name__)

class CanManagePagers(BasePermission):
    message = "Çağrı cihazlarını yönetme yetkiniz yok."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        user = request.user
        if user.user_type == 'business_owner':
            return True
        if user.user_type == 'staff' and 'manage_pagers' in user.staff_permissions:
            return True
        # Adminler de yönetebilir (opsiyonel, Django admini zaten yetkili)
        # if user.is_superuser:
        #     return True
        return False

    def has_object_permission(self, request, view, obj: Pager):
        user = request.user
        user_business = get_user_business(user) # Bu fonksiyonun doğru import edildiğinden emin olun
        
        # Adminler tüm objelere erişebilir (opsiyonel)
        # if user.is_superuser:
        #     return True
        
        if user_business and obj.business == user_business:
            return True
        return False


class PagerViewSet(viewsets.ModelViewSet):
    """
    Çağrı cihazlarını (Pager) yönetmek için API endpoint'leri.
    """
    serializer_class = PagerSerializer
    permission_classes = [IsAuthenticated, CanManagePagers]

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)

        if user_business:
            return Pager.objects.filter(business=user_business).select_related(
                'business',
                'current_order',
                'current_order__table',
                'current_order__customer'
            ).order_by('name', 'device_id')
        # if user.is_superuser:
        #     return Pager.objects.all().select_related('business', 'current_order')
        return Pager.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        user_business = get_user_business(user)
        if not user_business:
            raise PermissionDenied("Bu işlem için yetkili bir işletmeniz bulunmuyor.")
        
        device_id = serializer.validated_data.get('device_id')
        if Pager.objects.filter(business=user_business, device_id=device_id).exists():
            raise ValidationError({"device_id": "Bu cihaz ID'si zaten bu işletmede kayıtlı."})

        instance = serializer.save(business=user_business)
        logger.info(f"Pager #{instance.id} ({instance.device_id}) işletme '{user_business.name}' için oluşturuldu.")
        
        # Yeni pager eklendiğinde bildirim gönder (signals.py içindeki fonksiyonu çağır)
        from ..signals import send_pager_status_update_notification_on_commit
        transaction.on_commit(lambda: send_pager_status_update_notification_on_commit(instance.id))

    def perform_update(self, serializer):
        instance_before_update = self.get_object()
        old_status = instance_before_update.status
        old_current_order_id = instance_before_update.current_order_id

        device_id = serializer.validated_data.get('device_id', instance_before_update.device_id)
        if device_id != instance_before_update.device_id and \
           Pager.objects.filter(business=instance_before_update.business, device_id=device_id).exclude(pk=instance_before_update.pk).exists():
            raise ValidationError({"device_id": "Bu cihaz ID'si zaten bu işletmede başka bir pager için kayıtlı."})

        instance = serializer.save()
        logger.info(f"Pager #{instance.id} ({instance.device_id}) güncellendi.")

        new_current_order_id = instance.current_order_id # Save sonrası instance'tan al
        if instance.status != old_status or new_current_order_id != old_current_order_id:
            from ..signals import send_pager_status_update_notification_on_commit
            transaction.on_commit(lambda: send_pager_status_update_notification_on_commit(instance.id))
        
        if instance.status != 'in_use' and instance.current_order is not None:
            logger.info(f"Pager #{instance.id} durumu '{instance.get_status_display()}' olarak güncellendi, sipariş bağlantısı kaldırılıyor.")
            instance.current_order = None
            instance.save(update_fields=['current_order'])
            # Bu save işlemi Pager için post_save sinyalini tekrar tetikleyebilir.
            # Eğer `send_pager_status_update_notification_on_commit` `update_fields` kontrolü yapıyorsa sorun olmaz.


    def perform_destroy(self, instance: Pager):
        pager_id_for_notification = instance.id
        pager_device_id_for_log = instance.device_id
        
        logger.info(f"Pager ID {pager_id_for_notification} (Device ID: {pager_device_id_for_log}) sistemden siliniyor...")
        instance.delete() # Bu işlem Pager.pre_delete ve Pager.post_delete sinyallerini tetikleyebilir (eğer varsa)
        logger.info(f"Pager ID {pager_id_for_notification} (Device ID: {pager_device_id_for_log}) sistemden silindi.")
        
        # Silindiğine dair bildirim gönder (opsiyonel, istemci tarafında ID ile listeden kaldırılabilir)
        # from ..signals import send_pager_delete_notification # Ayrı bir fonksiyon olabilir
        # transaction.on_commit(lambda: send_pager_delete_notification(pager_id_for_notification, instance.business_id))
        # Ya da genel bir "liste güncellendi" olayı. Şimdilik sinyal Pager silindiğinde bir şey yapmıyor.


    @action(detail=True, methods=['post'], url_path='update-status')
    def update_pager_status(self, request, pk=None):
        pager = self.get_object()
        new_status = request.data.get('status')

        valid_statuses = [choice[0] for choice in Pager.PAGER_STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response({"detail": f"Geçersiz durum: '{new_status}'. Geçerli durumlar: {', '.join(valid_statuses)}"}, status=status.HTTP_400_BAD_REQUEST)

        if pager.status == new_status:
            return Response({"detail": f"Çağrı cihazı zaten '{pager.get_status_display()}' durumunda."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            pager.status = new_status
            if new_status != 'in_use' and pager.current_order:
                logger.info(f"Pager #{pager.id} durumu '{new_status}' olarak güncellendi, Order #{pager.current_order.id} ile bağlantısı kaldırılıyor.")
                # Order modelindeki assigned_pager_instance OneToOne olduğu için Pager.current_order'ı null yapmak yeterli.
                pager.current_order = None 
            # Eğer 'in_use' yapılıyorsa ama current_order None ise, bu durum sipariş atama ile yönetilmeli.
            # Bu action sadece durumu değiştirir.
            pager.save(update_fields=['status', 'current_order'] if new_status != 'in_use' else ['status'])
            # Pager.save() kendi post_save sinyalini tetikleyip bildirimi gönderecek.
            
        serializer = self.get_serializer(pager)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='assign-to-order')
    def assign_to_order(self, request, pk=None):
        pager = self.get_object() # Çağrı cihazını al
        order_id_str = request.data.get('order_id')

        if not order_id_str:
            return Response({"detail": "Sipariş ID'si gereklidir."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order_id = int(order_id_str)
        except ValueError:
            return Response({"detail": "Geçersiz Sipariş ID formatı."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order_to_assign = Order.objects.get(id=order_id, business=pager.business)
        except Order.DoesNotExist:
            return Response({"detail": "Sipariş bulunamadı veya bu işletmeye ait değil."}, status=status.HTTP_404_NOT_FOUND)

        if order_to_assign.is_paid or order_to_assign.status in [Order.STATUS_COMPLETED, Order.STATUS_CANCELLED, Order.STATUS_REJECTED]:
            return Response({"detail": "Bu siparişe çağrı cihazı atanamaz (tamamlanmış/iptal edilmiş)."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # 1. Bu siparişe daha önce başka bir pager atanmışsa, o pager'ı boşa çıkar.
            if hasattr(order_to_assign, 'assigned_pager_instance') and order_to_assign.assigned_pager_instance:
                old_pager_for_order = order_to_assign.assigned_pager_instance
                if old_pager_for_order != pager: # Eğer farklı bir pager ise
                    old_pager_for_order.current_order = None
                    old_pager_for_order.status = 'available'
                    old_pager_for_order.save(update_fields=['current_order', 'status'])
                    logger.info(f"Order #{order_to_assign.id} için eski Pager #{old_pager_for_order.id} serbest bırakıldı.")
                    # Sinyal Pager.post_save üzerinden tetiklenecek.

            # 2. Seçilen bu pager (self.get_object()) daha önce başka bir siparişe atanmışsa, o siparişten ayır.
            if pager.current_order and pager.current_order != order_to_assign:
                logger.info(f"Pager #{pager.id} eski sipariş #{pager.current_order.id}'den ayrılıyor.")
                # Pager.current_order'ı None yapmak, Order.assigned_pager_instance'ı da None yapar (OneToOne)
                # Bu işlem save() ile yapılacağı için Pager'ın post_save sinyali tetiklenir.
                # Ancak burada direkt None yapıp sonra yeni order'ı atayacağız.

            # 3. Pager'ı yeni siparişe ata ve durumunu güncelle.
            pager.current_order = order_to_assign
            pager.status = 'in_use'
            pager.save(update_fields=['current_order', 'status'])
            logger.info(f"Pager #{pager.id} Order #{order_to_assign.id}'e atandı.")
            # Pager.save() kendi post_save sinyalini tetikleyip bildirimi gönderecek.
            
        serializer = self.get_serializer(pager)
        return Response(serializer.data, status=status.HTTP_200_OK)