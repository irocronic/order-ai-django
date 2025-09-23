# core/services/payment_terminal_service.py

import logging
from decimal import Decimal
from django.conf import settings
from django.utils.module_loading import import_string

from ..models import Order, PaymentTerminal

logger = logging.getLogger(__name__)

class PaymentTerminalServiceFactory:
    """
    Ayarlarda belirtilen aktif ödeme sağlayıcısı için doğru servis sınıfını
    dinamik olarak yükleyen ve başlatan fabrika sınıfı.
    """
    _service_instance = None

    @staticmethod
    def get_service():
        """
        Aktif ödeme sağlayıcısı servisini döndürür.
        Performans için singleton deseni kullanır.
        """
        if PaymentTerminalServiceFactory._service_instance is None:
            provider_key = settings.ACTIVE_PAYMENT_PROVIDER
            provider_config = settings.PAYMENT_PROVIDERS.get(provider_key)

            if not provider_config:
                raise NotImplementedError(f"'{provider_key}' ödeme sağlayıcısı için yapılandırma bulunamadı.")
            
            try:
                service_class_path = provider_config['service_class']
                ServiceClass = import_string(service_class_path)
                PaymentTerminalServiceFactory._service_instance = ServiceClass()
                logger.info(f"✅ Ödeme servisi başarıyla yüklendi: {provider_key}")
            except (ImportError, KeyError) as e:
                logger.error(f"Ödeme servisi yüklenemedi: {e}")
                raise NotImplementedError(f"'{provider_key}' için servis sınıfı yüklenemedi: {service_class_path}")
        
        return PaymentTerminalServiceFactory._service_instance

# Fonksiyonları fabrika üzerinden kullanmak için sarmalayıcılar
def create_payment(amount: Decimal, currency: str, order: Order, terminal: PaymentTerminal, **kwargs):
    service = PaymentTerminalServiceFactory.get_service()
    payment_intent_id = service.create_payment_intent(amount, currency, order, terminal, **kwargs)
    
    # process_payment_on_reader adımı her sağlayıcıda olmayabilir, servisin içinde halledilebilir.
    # Şimdilik bu adımı ayırıyoruz.
    service.process_payment_on_reader(payment_intent_id, terminal.provider_terminal_id)
    
    return payment_intent_id

def handle_webhook(request):
    service = PaymentTerminalServiceFactory.get_service()
    return service.handle_webhook(request)

def check_payment_status(order: Order):
    service = PaymentTerminalServiceFactory.get_service()
    return service.check_payment_status(order)