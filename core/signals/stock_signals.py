# core/signals/stock_signals.py (Düzeltilmiş Versiyon)

from django.db.models.signals import post_save
from django.dispatch import receiver
import logging
from django.db import transaction
# YENİ: Gerekli importlar
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from ..models import MenuItemVariant, Stock
# Artık bu import'a gerek yok, doğrudan channels kullanacağız
# from ..utils.notifications import send_websocket_notification 

logger = logging.getLogger(__name__)

# Bu sinyal aynı kalıyor
@receiver(post_save, sender=MenuItemVariant)
def create_stock_for_new_variant(sender, instance: MenuItemVariant, created: bool, **kwargs):
    if created:
        stock, stock_created = Stock.objects.get_or_create(variant=instance)
        if stock_created:
            logger.info(f"SİNYAL (Stok Oluşturma): Yeni varyant '{instance.name}' için stok kaydı oluşturuldu.")

# BU FONKSİYONU GÜNCELLEYİN
def check_and_notify_stock_alert(stock_instance):
    """ Stok uyarı durumunu kontrol eder ve gerekirse bildirim gönderir. """
    try:
        stock = stock_instance
        is_alert_active = (
            stock.track_stock and
            stock.alert_threshold is not None and
            stock.quantity <= stock.alert_threshold
        )
        
        # === YENİ: Channels katmanını al ===
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.error("Channel layer alınamadı, bildirim gönderilemiyor.")
            return

        business_id = stock.variant.menu_item.business_id
        group_name = f"business_{business_id}"
        
        # === YENİ: stock_views.py ile aynı formatta payload oluştur ===
        payload = {
            # Channels'ın bu mesajı işlemesi için 'type' anahtarı gereklidir.
            # Channels consumer'ınızda bu type'ı karşılayan bir metot olmalı.
            # Muhtemelen stock_status_update(self, event) şeklinde bir metodunuz var.
            "type": "stock_status_update",
            "event_type": "stock_alert", # Flutter tarafının olayı ayırt etmesi için
            "alert": is_alert_active,
            "variant_id": stock.variant.id,
            "variant_name": stock.variant.name,
            "product_name": stock.variant.menu_item.name,
            "current_quantity": stock.quantity,
            "alert_threshold": stock.alert_threshold,
        }

        # === YENİ: Mesajı doğrudan channels grubuna gönder ===
        async_to_sync(channel_layer.group_send)(group_name, payload)

        logger.info(f"Stok uyarısı bildirimi (Channels) gönderildi: Ürün: {stock.variant.name}, Uyarı Aktif: {is_alert_active}")

    except Exception as e:
        logger.error(f"Stok uyarısı bildirimi gönderilirken hata oluştu: {e}", exc_info=True)


@receiver(post_save, sender=Stock)
def handle_stock_update_and_notify(sender, instance: Stock, created: bool, update_fields=None, **kwargs):
    if created or (update_fields and ('quantity' in update_fields or 'alert_threshold' in update_fields or 'track_stock' in update_fields)):
        logger.info(f"SİNYAL (Stok Güncelleme): Stok ID {instance.id} için uyarı kontrolü tetiklendi.")
        transaction.on_commit(lambda: check_and_notify_stock_alert(instance))