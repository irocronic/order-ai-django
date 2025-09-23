# core/services/payment_service_factory.py

from core.models import Business
from .payment_providers.base import BasePaymentService
from .payment_providers.iyzico import IyzicoPaymentService
# from .payment_providers.paytr import PayTRPaymentService # Gelecekte eklenecek

class PaymentServiceFactory:
    """
    İşletmenin ayarlarına göre doğru ödeme servisi nesnesini oluşturan fabrika sınıfı.
    """
    _providers = {
        Business.PaymentProvider.IYZICO: IyzicoPaymentService,
        # Business.PaymentProvider.PAYTR: PayTRPaymentService,
    }

    @staticmethod
    def get_service(business: Business) -> BasePaymentService | None:
        """
        Verilen işletme için uygun ödeme servisini döndürür.
        Eğer bir sağlayıcı atanmamışsa veya desteklenmiyorsa None döner.
        """
        provider_key = business.payment_provider
        service_class = PaymentServiceFactory._providers.get(provider_key)

        if service_class:
            return service_class(business=business)
        
        return None