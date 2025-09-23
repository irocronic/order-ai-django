# core/services/base_payment_service.py


from abc import ABC, abstractmethod
from decimal import Decimal
from django.http import HttpRequest
from ..models import Order, PaymentTerminal

class BasePaymentTerminalService(ABC):
    """
    Tüm ödeme terminali sağlayıcılarının uygulaması gereken soyut temel sınıf.
    Bu sınıf, farklı sağlayıcılar arasında tutarlı bir arayüz sağlar.
    """

    @abstractmethod
    def create_payment_intent(self, amount: Decimal, currency: str, order: Order, terminal: PaymentTerminal, **kwargs):
        """
        Ödeme niyetini veya işlemini başlatır.
        Sağlayıcıya özgü bir işlem ID'si veya referansı döndürmelidir.
        """
        pass

    @abstractmethod
    def process_payment_on_reader(self, payment_intent_id: str, terminal_id: str):
        """
        Oluşturulan ödeme niyetini fiziksel cihaza gönderir.
        (Tüm sağlayıcılarda bu adım olmayabilir, gerekirse boş bırakılabilir.)
        """
        pass
    
    @abstractmethod
    def handle_webhook(self, request: HttpRequest):
        """
        Sağlayıcıdan gelen webhook isteğini işler.
        İmza doğrulaması ve payload'un ayrıştırılması burada yapılır.
        Başarılı bir ödeme sonrası (Order, Payment) nesnelerini döndürebilir.
        """
        pass

    @abstractmethod
    def check_payment_status(self, order: Order):
        """
        Bir siparişin ödeme durumunu manuel olarak sorgular.
        (Webhook'un gecikmesi durumunda kullanılır.)
        """
        pass