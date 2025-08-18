# core/signals/pager_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from asgiref.sync import async_to_sync
import logging

# Proje içi importlar
from ..models import Pager
from .order_signals import convert_decimals_to_strings # Diğer sinyal dosyasından yardımcı fonksiyonu import et

logger = logging.getLogger(__name__)

def send_pager_status_update_notification_on_commit(pager_id):
    try:
        pager_instance = Pager.objects.select_related('business', 'current_order').get(id=pager_id)
    except Pager.DoesNotExist:
        logger.error(f"SİNYAL (Pager on_commit): ID'si {pager_id} olan pager bulunamadı.")
        return

    if not pager_instance.business_id:
        logger.error(f"SİNYAL (Pager on_commit): Pager {pager_instance.id} için işletme bilgisi yok. Bildirim gönderilmedi.")
        return
    
    try:
        from makarna_project.asgi import sio
        if sio is None:
            logger.error("SİNYAL (Pager on_commit): makarna_project.asgi.sio instance'ı None! Bildirim gönderilemedi.")
            return
    except ImportError:
        logger.error("SİNYAL (Pager on_commit): makarna_project.asgi.sio import edilemedi! Bildirim gönderilemedi.")
        return
    
    business_room_name = f'business_{pager_instance.business_id}'
    payload = {
        'event_type': 'pager_status_updated',
        'pager_id': pager_instance.id,
        'device_id': pager_instance.device_id,
        'name': pager_instance.name,
        'status': pager_instance.status,
        'status_display': pager_instance.get_status_display(),
        'current_order_id': pager_instance.current_order_id,
        'message': f"Çağrı cihazı '{pager_instance.name or pager_instance.device_id}' durumu güncellendi: {pager_instance.get_status_display()}"
    }
    cleaned_payload = convert_decimals_to_strings(payload)
    
    logger.info(f"SİNYAL (Socket.IO Emit - Pager): Oda: {business_room_name}, Event: 'pager_event', Pager ID: {pager_instance.id}, Yeni Durum: {pager_instance.status}")
    async_to_sync(sio.emit)('pager_event', cleaned_payload, room=business_room_name)


@receiver(post_save, sender=Pager)
def pager_status_change_receiver(sender, instance: Pager, created: bool, update_fields=None, **kwargs):
    send_notification = False
    if created:
        send_notification = True
        logger.info(f"SİNYAL (Pager Created): Pager #{instance.id} ({instance.device_id}) oluşturuldu.")
    elif update_fields and ('status' in update_fields or 'current_order' in update_fields or 'name' in update_fields):
        send_notification = True
        logger.info(f"SİNYAL (Pager Updated): Pager #{instance.id} durumu/ataması/adı güncellendi. Alanlar: {update_fields}")
    
    if send_notification:
        transaction.on_commit(lambda: send_pager_status_update_notification_on_commit(instance.id))