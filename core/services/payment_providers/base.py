# core/services/payment_providers/base.py

from abc import ABC, abstractmethod
from core.models import Business, Order

class BasePaymentService(ABC):
    """
    Tüm ödeme sağlayıcı servisleri için temel arayüz.
    Her sağlayıcı bu sınıftan türemeli ve metotları implement etmelidir.
    """
    def __init__(self, business: Business):
        if not isinstance(business, Business):
            raise TypeError("business_instance, Business modelinden olmalıdır.")
        self.business = business
        self.api_key = business.payment_api_key
        self.secret_key = business.payment_secret_key

    @abstractmethod
    def create_payment(self, order: Order, card_details: dict):
        """
        Ödeme oturumu başlatır veya doğrudan ödeme alır.
        Sağlayıcıya özel mantık burada yer alır.
        """
        pass

    @abstractmethod
    def check_payment_status(self, transaction_id: str):
        """
        Bir ödemenin durumunu kontrol eder.
        """
        pass