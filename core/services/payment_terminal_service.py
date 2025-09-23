# core/services/payment_terminal_service.py

import uuid
import logging

logger = logging.getLogger(__name__)

class PaymentTerminalService:
    """
    POS cihazına bağlanıp ödeme başlatma/gönderme işlemlerini yöneten servis.
    Şimdilik demo/stub çalışıyor.
    """

    @staticmethod
    def create_payment(amount, order_id, terminal_id):
        """
        POS cihazına ödeme isteği gönder.
        Gerçek cihaz SDK'sı entegre edildiğinde burası değişecek.
        """
        logger.info(
            f"[POS] create_payment çağrıldı. amount={amount}, order_id={order_id}, terminal_id={terminal_id}"
        )

        # Burada gerçek ödeme sağlayıcısına API çağrısı yapılacak.
        # Şimdilik sahte bir ID üretelim:
        fake_payment_intent_id = f"pos_demo_{uuid.uuid4().hex[:12]}"
        return fake_payment_intent_id
