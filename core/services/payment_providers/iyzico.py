# core/services/payment_providers/iyzico.py

from .base import BasePaymentService
from core.models import Business, Order
import logging
from decimal import Decimal
from django.conf import settings
import qrcode
from io import BytesIO
import base64
import uuid

logger = logging.getLogger(__name__)

class IyzicoPaymentService(BasePaymentService):
    def __init__(self, business: Business):
        super().__init__(business)
        # Iyzico SDK'sını import et ve yapılandır
        self._setup_iyzico_sdk()

    def _setup_iyzico_sdk(self):
        """Iyzico SDK'sını yapılandır"""
        try:
            import iyzipay
            
            # ✅ Doğru yapılandırma
            self.options = {
                'api_key': self.api_key,
                'secret_key': self.secret_key,
                'base_url': iyzipay.SANDBOX_BASE_URL if getattr(settings, 'DEBUG', False) else iyzipay.LIVE_BASE_URL
            }
            
            logger.info(f"Iyzico SDK yapılandırıldı - Environment: {'SANDBOX' if getattr(settings, 'DEBUG', False) else 'LIVE'}")
            logger.info(f"API Key: {self.api_key[:10]}..." if self.api_key else "API Key: None")
                
        except ImportError:
            logger.error("iyzipay kütüphanesi bulunamadı. 'pip install iyzipay' ile yükleyin.")
            raise ImportError("iyzipay kütüphanesi yüklenmelidir")
        except Exception as e:
            logger.error(f"Iyzico SDK yapılandırma hatası: {str(e)}", exc_info=True)
            raise Exception(f"Iyzico SDK yapılandırma hatası: {str(e)}")

    def create_payment(self, order: Order, card_details: dict):
        """Normal kart ödeme implementasyonu"""
        logger.info(f"Iyzico normal ödeme işlemi başlatılıyor: Order #{order.id}")
        # TODO: Gelecekte implementasyonu tamamlanacak
        return {"status": "success", "transaction_id": f"iyzico_{order.id}"}

    def create_qr_payment_request(self, order: Order):
        """
        Raporda önerilen yaklaşım: Checkout Form + QR Generation
        1. Iyzico Checkout Form ile ödeme oturumu başlat
        2. Dönen URL'yi QR kod'una çevir
        """
        try:
            import iyzipay
            
            logger.info(f"Iyzico QR ödeme oluşturma (Checkout Form): Order #{order.id}")
            
            # ✅ API Key kontrolü
            if not self.api_key or not self.secret_key:
                logger.error("Iyzico API anahtarları eksik")
                raise Exception("İşletme için Iyzico API anahtarları yapılandırılmamış")
            
            # 1. Checkout Form için request hazırla
            request_data = {
                'locale': iyzipay.LOCALE.TR,
                'conversationId': f'order-{order.id}-{str(order.uuid)[:8]}',
                'price': str(order.grand_total.quantize(Decimal('0.01'))),
                'paidPrice': str(order.grand_total.quantize(Decimal('0.01'))),
                'currency': iyzipay.CURRENCY.TRY,
                'basketId': str(order.id),
                'paymentGroup': iyzipay.PAYMENT_GROUP.PRODUCT,
                'callbackUrl': f'{settings.BASE_URL}/api/iyzico/callback/',
                'enabledInstallments': [1],  # Tek çekim
                'buyer': self._prepare_buyer_info(order),
                'shippingAddress': self._prepare_address_info(order, 'shipping'),
                'billingAddress': self._prepare_address_info(order, 'billing'),
                'basketItems': self._prepare_basket_items(order),
            }
            
            logger.debug(f"Checkout Form request data hazırlandı: {request_data['conversationId']}")
            
            # 2. ✅ Doğru Checkout Form initialize
            checkout_form_initialize = iyzipay.CheckoutFormInitialize()
            result = checkout_form_initialize.create(request_data, self.options)
            
            logger.info(f"Checkout Form yanıtı - Status: {result.status}")
            
            if result.status == 'success':
                payment_url = result.payment_page_url
                transaction_token = result.token
                
                logger.info(f"Checkout Form başarıyla oluşturuldu. Token: {transaction_token}")
                
                # 3. Payment URL'ini QR kod'una çevir
                qr_data_string = self._generate_qr_code_string(payment_url)
                
                return {
                    "qr_data": qr_data_string,  # Flutter QR widget'ı için URL
                    "transaction_id": transaction_token
                }
            else:
                error_message = result.error_message if hasattr(result, 'error_message') else 'Checkout form oluşturulamadı'
                logger.error(f"Iyzico Checkout Form hatası: {error_message}")
                
                # ✅ Hata detayları logla
                if hasattr(result, 'error_code'):
                    logger.error(f"Hata kodu: {result.error_code}")
                if hasattr(result, 'error_group'):
                    logger.error(f"Hata grubu: {result.error_group}")
                    
                raise Exception(f"Iyzico Checkout Form hatası: {error_message}")
                
        except ImportError:
            logger.error("iyzipay kütüphanesi bulunamadı")
            raise Exception("iyzipay kütüphanesi yüklenmemiş")
        except Exception as e:
            logger.error(f"QR ödeme oluşturma hatası: {str(e)}", exc_info=True)
            raise Exception(f"QR ödeme oluşturma hatası: {str(e)}")

    def _generate_qr_code_string(self, payment_url):
        """
        Ödeme URL'ini QR kod string'ine çevir
        Flutter'da QrImageView widget'ı bu string'i kullanacak
        """
        try:
            # QR kod oluştur (sadece URL string'ini döndür)
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(payment_url)
            qr.make(fit=True)
            
            # Flutter için sadece URL string'ini döndür
            # Flutter'daki QrImageView widget'ı bu URL'yi kullanarak QR kodu oluşturacak
            logger.debug(f"QR kod verisi oluşturuldu: {payment_url}")
            return payment_url
            
        except Exception as e:
            logger.error(f"QR kod oluşturma hatası: {str(e)}")
            # Hata durumunda da URL'yi döndür
            return payment_url

    def check_payment_status(self, transaction_id: str):
        """
        Checkout Form token'ı ile ödeme durumunu kontrol et
        """
        try:
            import iyzipay
            
            logger.debug(f"Iyzico ödeme durumu sorgulanıyor: {transaction_id}")
            
            request_data = {
                'locale': iyzipay.LOCALE.TR,
                'conversationId': f'check-{transaction_id}',
                'token': transaction_id
            }
            
            # ✅ Doğru Checkout Form sorgulama
            checkout_form = iyzipay.CheckoutForm()
            result = checkout_form.retrieve(request_data, self.options)
            
            if result.status == 'success':
                payment_status = result.payment_status
                
                # Iyzico status mapping
                status_mapping = {
                    'SUCCESS': 'paid',
                    'FAILURE': 'failed',
                    'INIT_THREEDS': 'pending',
                    'CALLBACK_THREEDS': 'pending',
                    'BKM_POS_SELECTED': 'pending',
                    'WAITING': 'pending'
                }
                
                mapped_status = status_mapping.get(payment_status, 'pending')
                logger.debug(f"Ödeme durumu - Token: {transaction_id}, Status: {payment_status} -> {mapped_status}")
                
                return {"status": mapped_status}
            else:
                error_message = result.error_message if hasattr(result, 'error_message') else 'Durum sorgulanamadı'
                logger.warning(f"Iyzico durum sorgulama hatası: {error_message}")
                return {"status": "pending"}
                
        except ImportError:
            logger.error("iyzipay kütüphanesi bulunamadı")
            return {"status": "pending"}
        except Exception as e:
            logger.error(f"Ödeme durumu sorgulama hatası: {str(e)}", exc_info=True)
            return {"status": "pending"}

    def _prepare_buyer_info(self, order: Order):
        """Alıcı bilgilerini Iyzico formatında hazırla"""
        return {
            'id': f'buyer-{order.id}',
            'name': order.customer_name or 'Ad',
            'surname': 'Soyad',
            'gsmNumber': order.customer_phone or '+905350000000',
            'email': f'order{order.id}@orderai.com',
            'identityNumber': '74300864791',
            'lastLoginDate': '2023-01-01 00:00:00',
            'registrationDate': '2023-01-01 00:00:00',
            'registrationAddress': 'İstanbul, Türkiye',
            'ip': '127.0.0.1',
            'city': 'İstanbul',
            'country': 'Turkey',
            'zipCode': '34000'
        }

    def _prepare_address_info(self, order: Order, address_type: str):
        """Adres bilgilerini Iyzico formatında hazırla"""
        return {
            'contactName': order.customer_name or 'Müşteri',
            'city': 'İstanbul',
            'country': 'Turkey',
            'address': f'{order.business.name} - {address_type.title()} Address',
            'zipCode': '34000'
        }

    def _prepare_basket_items(self, order: Order):
        """Sipariş öğelerini Iyzico formatına çevir"""
        basket_items = []
        
        for item in order.order_items.all():
            item_name = item.menu_item.name
            if item.variant:
                item_name += f' ({item.variant.name})'
                
            # Ekstralar varsa isimde belirt
            if hasattr(item, 'extras') and item.extras.exists():
                extra_names = [extra.variant.name for extra in item.extras.all()]
                if extra_names:
                    item_name += f' + {", ".join(extra_names)}'
                
            category_name = 'Genel'
            if item.menu_item.category:
                category_name = item.menu_item.category.name
            
            basket_items.append({
                'id': f'item-{item.id}',
                'name': item_name[:255],  # Iyzico karakter sınırı
                'category1': category_name[:255],
                'category2': 'Restoran',
                'itemType': iyzipay.BASKET_ITEM_TYPE.VIRTUAL,
                'price': str((item.price * item.quantity).quantize(Decimal('0.01')))
            })
        
        return basket_items