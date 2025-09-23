# core/services/stripe_terminal_service.py (YENİ DOSYA)

import stripe
from django.conf import settings
import logging
from decimal import Decimal

from .base_payment_service import BasePaymentTerminalService # Yeni import
from ..models import Order, Payment, PaymentTerminal

logger = logging.getLogger(__name__)

class StripeTerminalService(BasePaymentTerminalService): # Base sınıftan türet
    """
    Stripe Terminal API'si ile iletişim kuran servis.
    """
    def __init__(self):
        if not settings.STRIPE_SECRET_KEY:
            raise Exception("Stripe API anahtarı (STRIPE_SECRET_KEY) ayarlanmamış.")
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def create_payment_intent(self, amount: Decimal, currency: str, order: Order, terminal: PaymentTerminal, **kwargs):
        try:
            amount_in_cents = int(amount * 100)
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_in_cents,
                currency=currency.lower(),
                payment_method_types=['card_present'],
                capture_method='manual',
                metadata={
                    'order_id': str(order.id),
                    'terminal_id': terminal.provider_terminal_id
                }
            )
            logger.info(f"[Stripe] Sipariş #{order.id} için PaymentIntent oluşturuldu: {payment_intent.id}")
            return payment_intent.id
        except stripe.error.StripeError as e:
            logger.error(f"[Stripe] PaymentIntent oluşturma hatası: {e}")
            raise Exception(f"Stripe PaymentIntent oluşturulamadı: {e}")

    def process_payment_on_reader(self, payment_intent_id: str, terminal_id: str):
        try:
            reader = stripe.terminal.Reader.process_payment_intent(
                terminal_id,
                payment_intent=payment_intent_id,
            )
            logger.info(f"[Stripe] Ödeme isteği ({payment_intent_id}) terminale ({terminal_id}) gönderildi.")
            return reader
        except stripe.error.StripeError as e:
            logger.error(f"[Stripe] Ödeme isteği terminale gönderilirken hata: {e}")
            # Gerekirse ödeme niyetini iptal et
            stripe.PaymentIntent.cancel(payment_intent_id)
            raise Exception(f"Ödeme terminale gönderilemedi: {e}")

    def handle_webhook(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        if not webhook_secret:
            logger.error("[Stripe Webhook] Webhook secret ayarlanmamış!")
            raise ValueError("Webhook secret not configured")

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            logger.error(f"[Stripe Webhook] İmza doğrulama hatası: {e}")
            raise PermissionError("Invalid webhook signature")

        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            order_id = payment_intent.get('metadata', {}).get('order_id')
            if not order_id:
                logger.error("[Stripe Webhook] Başarılı ödeme event'i içinde 'order_id' bulunamadı.")
                return None, None
            
            order = Order.objects.get(id=int(order_id))
            amount_received = Decimal(payment_intent['amount_received']) / 100
            
            payment = Payment.objects.create(
                order=order,
                payment_type='credit_card',
                amount=amount_received
            )
            return order, payment
        
        # Diğer event tipleri (failed, canceled) burada işlenebilir
        return None, None

    def check_payment_status(self, order: Order):
        # Stripe için bu özellik, Payment Intent'i ID'si ile sorgulayarak implemente edilebilir
        # Şimdilik placeholder olarak bırakalım.
        logger.warning("Stripe için `check_payment_status` henüz implemente edilmedi.")
        return "processing" # veya "succeeded", "failed"