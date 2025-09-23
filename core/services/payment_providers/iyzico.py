# core/services/payment_providers/iyzico.py

from .base import BasePaymentService
from core.models import Business, Order
import requests
import json
import logging
from decimal import Decimal
from django.conf import settings
import hashlib
import base64
import time

logger = logging.getLogger(__name__)

class IyzicoPaymentService(BasePaymentService):
    def __init__(self, business: Business):
        super().__init__(business)
        # Iyzico API'si için gerekli ayarları yap
        self.api_key = self.api_key
        self.secret_key = self.secret_key
        self.base_url = self._get_base_url()

    def _get_base_url(self):
        """Ortam tipine göre API URL'ini döndür"""
        if getattr(settings, 'DEBUG', False):
            return 'https://sandbox-api.iyzipay.com'  # Test ortamı
        else:
            return 'https://api.iyzipay.com'  # Production ortamı

    def _generate_auth_string(self, request_body):
        """Iyzico için authorization string oluştur"""
        random_string = str(int(time.time() * 1000))
        auth_string = f"apiKey:{self.api_key}&randomKey:{random_string}&signature:{self._generate_signature(request_body, random_string)}"
        return base64.b64encode(auth_string.encode()).decode()

    def _generate_signature(self, request_body, random_string):
        """Iyzico signature oluştur"""
        signature_data = f"{self.api_key}{random_string}{self.secret_key}{request_body}"
        return hashlib.sha1(signature_data.encode()).hexdigest()

    def create_payment(self, order: Order, card_details: dict):
        logger.info(f"Iyzico normal ödeme işlemi başlatılıyor: Order #{order.id}")
        # TODO: Normal kart ödeme implementasyonu
        return {"status": "success", "transaction_id": f"iyzico_{order.id}"}

    def create_qr_payment_request(self, order: Order):
        """
        Iyzico API'sini kullanarak bir sipariş için QR ödeme isteği oluşturur.
        """
        try:
            # Sipariş öğelerini hazırla
            basket_items = self._prepare_basket_items(order)
            
            request_data = {
                'locale': 'tr',
                'conversationId': f'order-{order.id}-{str(order.uuid)[:8]}',
                'price': str(order.grand_total.quantize(Decimal('0.01'))),
                'paidPrice': str(order.grand_total.quantize(Decimal('0.01'))),
                'currency': order.business.currency_code,
                'paymentGroup': 'PRODUCT',
                'basketId': str(order.id),
                'basketItems': basket_items,
                'callbackUrl': f'{settings.BASE_URL}/api/iyzico/callback/',
            }
            
            logger.info(f"Iyzico QR oluşturma isteği: Order #{order.id}")
            
            # JSON string oluştur
            request_json = json.dumps(request_data, separators=(',', ':'))
            
            # Authorization header oluştur
            auth_header = self._generate_auth_string(request_json)
            
            # API isteği gönder
            headers = {
                'Authorization': f'IYZWSv2 {auth_header}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # QR Code endpoint'i (Iyzico'nun gerçek QR endpoint'i)
            url = f'{self.base_url}/payment/qr/initialize'
            
            response = requests.post(url, headers=headers, data=request_json, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"Iyzico QR yanıtı alındı: Order #{order.id}")
                
                if response_data.get('status') == 'success':
                    return {
                        "qr_data": response_data.get('qrCodeImageUrl'),  # QR kod URL'i
                        "transaction_id": response_data.get('token')  # Transaction token
                    }
                else:
                    error_message = response_data.get('errorMessage', 'QR ödeme oluşturulamadı')
                    logger.error(f"Iyzico QR hatası: {error_message}")
                    raise Exception(f"Iyzico QR oluşturma hatası: {error_message}")
            else:
                logger.error(f"Iyzico API hatası: {response.status_code} - {response.text}")
                raise Exception(f"Iyzico API bağlantı hatası: {response.status_code}")
                
        except requests.RequestException as e:
            logger.error(f"Iyzico API isteği hatası: {str(e)}", exc_info=True)
            raise Exception(f"Iyzico API bağlantı hatası: {str(e)}")
        except Exception as e:
            logger.error(f"QR ödeme oluşturma hatası: {str(e)}", exc_info=True)
            raise

    def check_payment_status(self, transaction_id: str):
        """
        Iyzico API'sini kullanarak bir QR ödemesinin durumunu kontrol eder.
        """
        try:
            request_data = {
                'locale': 'tr',
                'conversationId': f'check-{transaction_id}',
                'token': transaction_id  # QR token
            }

            logger.debug(f"Iyzico ödeme durumu sorgulanıyor: {transaction_id}")
            
            request_json = json.dumps(request_data, separators=(',', ':'))
            auth_header = self._generate_auth_string(request_json)
            
            headers = {
                'Authorization': f'IYZWSv2 {auth_header}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            url = f'{self.base_url}/payment/qr/retrieve'
            response = requests.post(url, headers=headers, data=request_json, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                
                if response_data.get('status') == 'success':
                    payment_status = response_data.get('paymentStatus')
                    
                    status_mapping = {
                        'SUCCESS': 'paid',
                        'FAILURE': 'failed',
                        'INIT_THREEDS': 'pending',
                        'WAITING': 'pending',
                        'BKM_POS_SELECTED': 'pending'
                    }
                    
                    mapped_status = status_mapping.get(payment_status, 'pending')
                    logger.debug(f"Ödeme durumu - Transaction: {transaction_id}, Status: {payment_status} -> {mapped_status}")
                    
                    return {"status": mapped_status}
                else:
                    error_message = response_data.get('errorMessage', 'Durum sorgulanamadı')
                    logger.warning(f"Iyzico durum sorgulama hatası: {error_message}")
                    return {"status": "pending"}
            else:
                logger.warning(f"Iyzico API hatası: {response.status_code}")
                return {"status": "pending"}
                
        except requests.RequestException as e:
            logger.error(f"Ödeme durumu sorgulama hatası: {str(e)}")
            return {"status": "pending"}
        except Exception as e:
            logger.error(f"Ödeme durumu sorgulama hatası: {str(e)}", exc_info=True)
            return {"status": "pending"}

    def _prepare_basket_items(self, order: Order):
        """Sipariş öğelerini Iyzico formatına çevir"""
        basket_items = []
        
        for item in order.order_items.all():
            item_name = item.menu_item.name
            if item.variant:
                item_name += f' ({item.variant.name})'
                
            category_name = 'Genel'
            if item.menu_item.category:
                category_name = item.menu_item.category.name
            
            basket_items.append({
                'id': f'item-{item.id}',
                'name': item_name,
                'category1': category_name,
                'category2': 'Restoran',
                'itemType': 'VIRTUAL',
                'price': str((item.price * item.quantity).quantize(Decimal('0.01')))
            })
        
        return basket_items