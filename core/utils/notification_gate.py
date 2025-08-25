# core/utils/notification_gate.py

from django.core.cache import cache
from ..models import NotificationSetting
import logging

logger = logging.getLogger(__name__)

# Önbellek anahtarı için bir ön ek
CACHE_PREFIX = "notification_setting_"
# Ayarların önbellekte ne kadar süre kalacağı (saniye cinsinden)
CACHE_TIMEOUT = 300  # 5 dakika

def is_notification_active(event_type: str) -> bool:
    """
    Bir bildirim türünün aktif olup olmadığını kontrol eder.
    Sonucu performansı artırmak için önbelleğe alır.
    """
    cache_key = f"{CACHE_PREFIX}{event_type}"
    
    # 1. Önbelleği kontrol et
    is_active = cache.get(cache_key)
    
    if is_active is not None:
        # Önbellekte bulundu, doğrudan döndür
        return is_active

    # 2. Önbellekte yoksa, veritabanından sorgula
    try:
        setting = NotificationSetting.objects.get(event_type=event_type)
        is_active = setting.is_active
    except NotificationSetting.DoesNotExist:
        # Eğer ayar veritabanında yoksa (yeni eklenen bir bildirim tipi gibi),
        # varsayılan olarak aktif kabul edelim ki sistem durmasın.
        logger.warning(f"'{event_type}' için bildirim ayarı bulunamadı. Varsayılan olarak AKTİF kabul ediliyor.")
        is_active = True
    
    # 3. Sonucu önbelleğe kaydet
    cache.set(cache_key, is_active, CACHE_TIMEOUT)
    
    return is_active