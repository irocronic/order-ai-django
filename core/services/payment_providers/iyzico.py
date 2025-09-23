# core/services/payment_providers/iyzico.py

from .base import BasePaymentService
from core.models import Order

class IyzicoPaymentService(BasePaymentService):
    def create_payment(self, order: Order, card_details: dict):
        # Iyzico API'sine istek atacak kod buraya gelecek.
        # self.api_key ve self.secret_key'i kullanarak Iyzico ile iletişim kur.
        print(f"Iyzico ile ödeme oluşturuluyor: Order #{order.id}, API Key: {self.api_key[:5]}...")
        # ...
        # Başarılı olursa transaction ID, başarısız olursa hata döndür.
        return {"status": "success", "transaction_id": "iyzico_12345"}

    def check_payment_status(self, transaction_id: str):
        print(f"Iyzico ödeme durumu kontrol ediliyor: {transaction_id}")
        return {"status": "paid"}