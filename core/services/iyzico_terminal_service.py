# core/services/iyzico_terminal_service.py


from decimal import Decimal
import logging
import json
# Iyzico'nun kendi kütüphanesini import ettiğinizi varsayalım
# import iyzico

from .base_payment_service import BasePaymentTerminalService
from ..models import Order, Payment, PaymentTerminal
from django.conf import settings

logger = logging.getLogger(__name__)

class IyzicoTerminalService(BasePaymentTerminalService):
    """
    Iyzico POS API'si ile iletişim kuran servis. (ÖRNEK)
    """
    def __init__(self):
        # Iyzico API anahtarlarını settings'den al
        # self.options = {
        #     'api_key': settings.IYZICO_API_KEY,
        #     'secret_key': settings.IYZICO_SECRET_KEY,
        #     'base_url': settings.IYZICO_BASE_URL
        # }
        pass

    def create_payment_intent(self, amount: Decimal, currency: str, order: Order, terminal: PaymentTerminal, **kwargs):
        logger.info(f"[Iyzico] Sipariş #{order.id} için ödeme isteği oluşturuluyor.")
        # Iyzico'ya özgü API çağrıları burada yapılır.
        # Örneğin, bir ödeme başlatma isteği gönderilir ve bir 'conversationId' alınır.
        # Bu ID'yi Payment modelinde saklamak için bir JSONField kullanabilirsiniz.
        conversation_id = f"conv_{order.id}_{terminal.id}"
        print(f"Iyzico'ya {amount} {currency} tutarında istek gönderildi. Conversation ID: {conversation_id}")
        return conversation_id # Iyzico'dan dönen işlem ID'si

    def process_payment_on_reader(self, payment_intent_id: str, terminal_id: str):
        # Iyzico'nun bazı POS çözümlerinde bu adım olmayabilir.
        logger.info("[Iyzico] process_payment_on_reader bu sağlayıcı için geçerli değil.")
        pass

    def handle_webhook(self, request):
        # Iyzico webhook'u için imza doğrulama ve payload işleme mantığı burada yer alır.
        # Bu kısım Iyzico dokümantasyonuna göre doldurulmalıdır.
        payload = json.loads(request.body)
        
        # Örnek: Webhook doğrulaması ve işlenmesi
        # iyzico_header = request.headers.get('x-iyzico-signature')
        # if not self.verify_signature(payload, iyzico_header):
        #     raise PermissionError("Invalid Iyzico webhook signature")

        if payload.get('status') == 'SUCCESS':
            order_id = payload.get('merchantOrderId')
            order = Order.objects.get(id=int(order_id))
            amount_paid = Decimal(payload.get('paidPrice'))
            
            payment = Payment.objects.create(
                order=order,
                payment_type='credit_card',
                amount=amount_paid
            )
            return order, payment
        
        return None, None
        
    def check_payment_status(self, order: Order):
        # Iyzico API'si üzerinden siparişin ödeme durumunu sorgulama
        logger.warning("Iyzico için `check_payment_status` henüz implemente edilmedi.")
        return "processing"