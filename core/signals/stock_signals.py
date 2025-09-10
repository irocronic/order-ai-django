# core/signals/stock_signals.py (Düzeltilmiş Versiyon)

from django.db.models.signals import post_save
from django.dispatch import receiver
import logging
from django.db import transaction

from ..models import MenuItemVariant, Stock
from ..utils.notifications import send_websocket_notification

logger = logging.getLogger(__name__)

@receiver(post_save, sender=MenuItemVariant)
def create_stock_for_new_variant(sender, instance: MenuItemVariant, created: bool, **kwargs):
    """
    Yeni bir MenuItemVariant oluşturulduğunda, onun için otomatik olarak
    bir Stock kaydı da oluşturur. Bu, stok düşme hatalarını önler.
    """
    if created:
        stock, stock_created = Stock.objects.get_or_create(variant=instance)
        if stock_created:
            logger.info(f"SİNYAL (Stok Oluşturma): Yeni varyant '{instance.name}' (ID: {instance.id}) için stok kaydı otomatik olarak oluşturuldu. Mevcut stok: {stock.quantity}")

def check_and_notify_stock_alert(stock_instance):
    """ Stok uyarı durumunu kontrol eder ve gerekirse bildirim gönderir. """
    try:
        stock = stock_instance
        is_alert_active = (
            stock.track_stock and
            stock.alert_threshold is not None and
            stock.quantity <= stock.alert_threshold
        )

        # Her durumda bir bildirim göndererek Flutter tarafının durumu güncellemesini sağlayalım.
        # Flutter tarafı, mevcut uyarı durumu ile gelen uyarı durumu farklıysa UI'ı günceller.
        payload = {
            'event_type': 'stock_alert',
            'alert': is_alert_active, # True veya False
            'variant_id': stock.variant.id,
            'variant_name': stock.variant.name,
            'product_name': stock.variant.menu_item.name,
            'current_quantity': stock.quantity,
            'alert_threshold': stock.alert_threshold,
        }
        business_id = stock.variant.menu_item.business_id
        send_websocket_notification(business_id, 'stock_alert', payload)
        logger.info(f"Stok uyarısı bildirimi gönderildi: Ürün: {stock.variant.name}, Uyarı Aktif: {is_alert_active}")

    except Exception as e:
        logger.error(f"Stok uyarısı bildirimi gönderilirken hata oluştu: {e}", exc_info=True)


@receiver(post_save, sender=Stock)
def handle_stock_update_and_notify(sender, instance: Stock, created: bool, update_fields=None, **kwargs):
    """
    Stok kaydı güncellendiğinde veya oluşturulduğunda, uyarı eşiğini kontrol eder
    ve anlık bildirim gönderir.
    """
    # Sadece miktar veya uyarı ayarları değiştiğinde tetikle
    if created or (update_fields and ('quantity' in update_fields or 'alert_threshold' in update_fields or 'track_stock' in update_fields)):
        logger.info(f"SİNYAL (Stok Güncelleme): Stok ID {instance.id} için uyarı kontrolü tetiklendi. Değişen alanlar: {update_fields}")
        # `on_commit` kullanarak veritabanı işlemi tamamlandıktan sonra bildirimin gönderilmesini sağlarız.
        transaction.on_commit(lambda: check_and_notify_stock_alert(instance))