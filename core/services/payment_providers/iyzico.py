# core/services/payment_providers/iyzico.py

from .base import BasePaymentService
from core.models import Business, Order
import iyzipay
import logging
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger(__name__)

class IyzicoPaymentService(BasePaymentService):
    def __init__(self, business: Business):  # Order değil Business olmalı
        super().__init__(business)
        # Iyzico API'si için gerekli ayarları yap
        self.options = {
            'api_key': self.api_key,
            'secret_key': self.secret_key,
            # Production/test ortam kontrolü
            'base_url': self._get_base_url()
        }
    
    def _get_base_url(self):
        """Ortam tipine göre API URL'ini döndür"""
        if getattr(settings, 'DEBUG', False):
            return 'https://sandbox-api.iyzipay.com'  # Test ortamı
        else:
            return 'https://api.iyzipay.com'  # Production ortamı

    def create_payment(self, order: Order, card_details: dict):
        # Normal kart ödemesi için implement edilecek
        logger.info(f"Iyzico normal ödeme işlemi başlatılıyor: Order #{order.id}")
        # TODO: Normal kart ödeme implementasyonu
        return {"status": "success", "transaction_id": f"iyzico_{order.id}"}

    def create_qr_payment_request(self, order: Order):
        """
        Iyzico API'sini kullanarak bir sipariş için dinamik TR Karekod verisi oluşturur.
        """
        try:
            # Sipariş öğelerini hazırla
            basket_items = self._prepare_basket_items(order)
            
            request = {
                'locale': 'tr',
                'conversationId': f'order-{order.id}-{order.uuid}',
                'price': str(order.grand_total.quantize(Decimal('0.01'))),
                'paidPrice': str(order.grand_total.quantize(Decimal('0.01'))),
                'currency': order.business.currency_code,
                'paymentGroup': 'PRODUCT',
                'basketId': str(order.id),
                'basketItems': basket_items,
                # Callback URL'leri (isteğe bağlı)
                'callbackUrl': f'{settings.BASE_URL}/api/iyzico/callback/',
            }
            
            logger.info(f"Iyzico QR oluşturma isteği: Order #{order.id}")
            
            # Iyzico API'sine isteği gönder
            qr_code_initialize = iyzipay.QRCode().create(request, self.options)
            
            if not qr_code_initialize:
                raise Exception("Iyzico API'sinden yanıt alınamadı")
            
            # API yanıtını işle
            response_json = qr_code_initialize.read().decode('utf-8')
            response_data = qr_code_initialize.json()

            logger.info(f"Iyzico QR yanıtı alındı: Order #{order.id}")

            if response_data.get('status') == 'success':
                return {
                    "qr_data": response_data.get('qrCodeUrl'),
                    "transaction_id": response_data.get('paymentId')
                }
            else:
                error_message = response_data.get('errorMessage', 'Bilinmeyen Iyzico hatası')
                logger.error(f"Iyzico QR hatası: {error_message}")
                raise Exception(f"Iyzico QR oluşturma hatası: {error_message}")
                
        except Exception as e:
            logger.error(f"QR ödeme oluşturma hatası: {str(e)}", exc_info=True)
            raise

    def check_payment_status(self, transaction_id: str):
        """
        Iyzico API'sini kullanarak bir QR ödemesinin durumunu kontrol eder.
        """
        try:
            request = {
                'locale': 'tr',
                'conversationId': f'check-{transaction_id}',
                'paymentId': transaction_id
            }

            logger.debug(f"Iyzico ödeme durumu sorgulanıyor: {transaction_id}")
            
            # Iyzico API'sine isteği gönder
            payment_details = iyzipay.Payment().retrieve(request, self.options)
            
            if not payment_details:
                logger.warning(f"Iyzico'dan yanıt alınamadı: {transaction_id}")
                return {"status": "pending"}
            
            response_data = payment_details.json()
            
            if response_data.get('status') == 'success':
                payment_status = response_data.get('paymentStatus')
                
                status_mapping = {
                    'SUCCESS': 'paid',
                    'FAILURE': 'failed',
                    'INIT': 'pending',
                    'WAITING_FOR_APPROVAL': 'pending'
                }
                
                mapped_status = status_mapping.get(payment_status, 'pending')
                logger.debug(f"Ödeme durumu - Transaction: {transaction_id}, Status: {payment_status} -> {mapped_status}")
                
                return {"status": mapped_status}
            else:
                error_message = response_data.get('errorMessage', 'Durum sorgulanamadı')
                logger.warning(f"Iyzico durum sorgulama hatası: {error_message}")
                return {"status": "pending"}  # Hata durumunda pending döndür
                
        except Exception as e:
            logger.error(f"Ödeme durumu sorgulama hatası: {str(e)}", exc_info=True)
            return {"status": "pending"}  # Hata durumunda pending döndür

    def _prepare_basket_items(self, order: Order):
        """Sipariş öğelerini Iyzico formatına çevir"""
        basket_items = []
        
        for item in order.order_items.all():
            basket_items.append({
                'id': f'item-{item.id}',
                'name': f'{item.menu_item.name}' + (f' ({item.variant.name})' if item.variant else ''),
                'category1': item.menu_item.category.name if item.menu_item.category else 'Genel',
                'category2': 'Restoran',
                'itemType': 'VIRTUAL',
                'price': str((item.price * item.quantity).quantize(Decimal('0.01')))
            })
        
        return basket_items