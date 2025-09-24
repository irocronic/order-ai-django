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
        logger.info(f"🔧 IyzicoPaymentService başlatılıyor - Business ID: {business.id}")
        # Iyzico SDK'sını import et ve yapılandır
        self._setup_iyzico_sdk()

    def _setup_iyzico_sdk(self):
        """Iyzico SDK'sını yapılandır"""
        try:
            logger.info("📦 iyzipay kütüphanesi import ediliyor...")
            import iyzipay
            logger.info("✅ iyzipay kütüphanesi başarıyla import edildi")
            
            # API Key kontrolü
            logger.info(f"🔑 API Keys kontrol ediliyor...")
            logger.info(f"   - api_key: {'✓ Var' if self.api_key else '✗ Eksik'} ({len(self.api_key) if self.api_key else 0} karakter)")
            logger.info(f"   - secret_key: {'✓ Var' if self.secret_key else '✗ Eksik'} ({len(self.secret_key) if self.secret_key else 0} karakter)")
            
            if not self.api_key or not self.secret_key:
                raise ValueError("Iyzico API Keys eksik veya boş")
            
            # Options yapılandırması
            self.options = iyzipay.Options()
            self.options.api_key = self.api_key
            self.options.secret_key = self.secret_key
            
            # Test/Production ortamına göre base URL ayarla
            if getattr(settings, 'DEBUG', False):
                self.options.base_url = "https://sandbox-api.iyzipay.com"
                logger.info("🧪 Iyzico SDK Sandbox ortamı için yapılandırıldı")
            else:
                self.options.base_url = "https://api.iyzipay.com"
                logger.info("🏭 Iyzico SDK Production ortamı için yapılandırıldı")
                
            logger.info("✅ Iyzico SDK başarıyla yapılandırıldı")
                
        except ImportError as e:
            logger.error(f"❌ iyzipay kütüphanesi import hatası: {e}")
            raise ImportError(f"iyzipay kütüphanesi yüklenemedi: {e}")
        except Exception as e:
            logger.error(f"❌ Iyzico SDK yapılandırma hatası: {e}")
            raise

    def create_payment(self, order: Order, card_details: dict):
        """Normal kart ödeme implementasyonu"""
        logger.info(f"Iyzico normal ödeme işlemi başlatılıyor: Order #{order.id}")
        # TODO: Gelecekte implementasyonu tamamlanacak
        return {"status": "success", "transaction_id": f"iyzico_{order.id}"}

    def create_qr_payment_request(self, order: Order):
        """
        DEBUG VERSİYONU - Raporda önerilen yaklaşım: Checkout Form + QR Generation
        1. Iyzico Checkout Form ile ödeme oturumu başlat
        2. Dönen URL'yi QR kod'una çevir
        """
        logger.info(f"🚀 Iyzico QR ödeme oluşturma başlıyor: Order #{order.id}")
        
        try:
            # 1. SDK Import kontrolü
            logger.info("📦 Step 1: iyzipay import kontrol ediliyor...")
            try:
                import iyzipay
                logger.info("✅ Step 1: iyzipay başarıyla import edildi")
            except ImportError as e:
                logger.error(f"❌ Step 1: iyzipay import hatası: {e}")
                raise Exception(f"iyzipay kütüphanesi yüklenemedi: {e}")
            
            # 2. Business ve Order bilgilerini kontrol et
            logger.info("🔍 Step 2: Order bilgileri kontrol ediliyor...")
            logger.info(f"   - Order ID: {order.id}")
            logger.info(f"   - Order UUID: {order.uuid}")
            logger.info(f"   - Grand Total: {order.grand_total}")
            logger.info(f"   - Business: {order.business.name}")
            logger.info(f"   - Currency: {order.business.currency_code or 'TRY'}")
            logger.info(f"   - BASE_URL: {settings.BASE_URL}")
            
            # 3. Request data hazırlama
            logger.info("⚙️ Step 3: Request data hazırlanıyor...")
            request_data = {
                'locale': 'tr',
                'conversationId': f'order-{order.id}-{str(order.uuid)[:8]}',
                'price': str(order.grand_total.quantize(Decimal('0.01'))),
                'paidPrice': str(order.grand_total.quantize(Decimal('0.01'))),
                'currency': order.business.currency_code or 'TRY',
                'basketId': str(order.id),
                'paymentGroup': 'PRODUCT',
                'callbackUrl': f'{settings.BASE_URL}/api/iyzico/callback/',
                'enabledInstallments': [1],  # Tek çekim
            }
            logger.info("✅ Step 3: Temel request data hazırlandı")
            
            # 4. Buyer bilgileri hazırlama
            logger.info("👤 Step 4: Buyer bilgileri hazırlanıyor...")
            try:
                buyer_info = self._prepare_buyer_info(order)
                request_data['buyer'] = buyer_info
                logger.info("✅ Step 4: Buyer bilgileri hazırlandı")
            except Exception as e:
                logger.error(f"❌ Step 4: Buyer bilgileri hazırlama hatası: {e}")
                raise
            
            # 5. Adres bilgileri hazırlama
            logger.info("🏠 Step 5: Adres bilgileri hazırlanıyor...")
            try:
                request_data['shippingAddress'] = self._prepare_address_info(order, 'shipping')
                request_data['billingAddress'] = self._prepare_address_info(order, 'billing')
                logger.info("✅ Step 5: Adres bilgileri hazırlandı")
            except Exception as e:
                logger.error(f"❌ Step 5: Adres bilgileri hazırlama hatası: {e}")
                raise
            
            # 6. Basket items hazırlama
            logger.info("🛒 Step 6: Basket items hazırlanıyor...")
            try:
                basket_items = self._prepare_basket_items(order)
                request_data['basketItems'] = basket_items
                logger.info(f"✅ Step 6: {len(basket_items)} adet basket item hazırlandı")
            except Exception as e:
                logger.error(f"❌ Step 6: Basket items hazırlama hatası: {e}")
                raise
            
            # 7. Request data logla
            logger.info("📋 Step 7: Final request data:")
            logger.info(f"   - conversationId: {request_data['conversationId']}")
            logger.info(f"   - price: {request_data['price']}")
            logger.info(f"   - currency: {request_data['currency']}")
            logger.info(f"   - callbackUrl: {request_data['callbackUrl']}")
            logger.info(f"   - basket items count: {len(request_data['basketItems'])}")
            
            # 8. Checkout Form initialize
            logger.info("🔄 Step 8: Iyzico Checkout Form initialize ediliyor...")
            try:
                checkout_form_initialize = iyzipay.CheckoutFormInitialize().create(request_data, self.options)
                logger.info("✅ Step 8: Checkout Form response alındı")
            except Exception as e:
                logger.error(f"❌ Step 8: Checkout Form initialize hatası: {e}")
                raise Exception(f"Checkout Form initialize hatası: {e}")
            
            # 9. Response analizi
            logger.info("🔍 Step 9: Response analiz ediliyor...")
            logger.info(f"   - Response type: {type(checkout_form_initialize)}")
            logger.info(f"   - Response attributes: {[attr for attr in dir(checkout_form_initialize) if not attr.startswith('_')]}")
            
            # 10. Status kontrolü
            if hasattr(checkout_form_initialize, 'status'):
                logger.info(f"✅ Step 10: Response status: {checkout_form_initialize.status}")
                
                if checkout_form_initialize.status == 'success':
                    logger.info("🎉 Checkout Form başarıyla oluşturuldu!")
                    
                    # URL ve token al
                    payment_url = getattr(checkout_form_initialize, 'payment_page_url', None)
                    transaction_token = getattr(checkout_form_initialize, 'token', None)
                    
                    logger.info(f"   - Payment URL: {payment_url}")
                    logger.info(f"   - Transaction Token: {transaction_token}")
                    
                    if not payment_url or not transaction_token:
                        logger.error("❌ Payment URL veya Token bulunamadı")
                        raise Exception("Payment URL veya Token bulunamadı")
                    
                    # QR kod string oluştur
                    logger.info("🔳 Step 11: QR kod verisi oluşturuluyor...")
                    qr_data_string = self._generate_qr_code_string(payment_url)
                    logger.info("✅ Step 11: QR kod verisi oluşturuldu")
                    
                    response_data = {
                        "qr_data": qr_data_string,
                        "transaction_id": transaction_token
                    }
                    
                    logger.info("🎊 Iyzico QR ödeme başarıyla oluşturuldu!")
                    return response_data
                    
                else:
                    error_message = getattr(checkout_form_initialize, 'error_message', 'Bilinmeyen hata')
                    error_code = getattr(checkout_form_initialize, 'error_code', 'NO_CODE')
                    logger.error(f"❌ Iyzico hatası - Status: {checkout_form_initialize.status}")
                    logger.error(f"❌ Error Code: {error_code}")
                    logger.error(f"❌ Error Message: {error_message}")
                    raise Exception(f"Iyzico hatası ({error_code}): {error_message}")
            else:
                logger.error("❌ Response'da status attribute'u bulunamadı")
                logger.error(f"❌ Response content: {str(checkout_form_initialize)}")
                raise Exception("Iyzico response'da status bulunamadı")
                
        except ImportError as e:
            logger.error(f"❌ iyzipay kütüphanesi hatası: {e}")
            raise Exception(f"iyzipay kütüphanesi yüklenmemiş: {e}")
        except Exception as e:
            logger.error(f"❌ QR ödeme oluşturma genel hatası: {str(e)}", exc_info=True)
            raise Exception(f"QR ödeme oluşturma hatası: {str(e)}")

    def _generate_qr_code_string(self, payment_url):
        """
        Ödeme URL'ini QR kod string'ine çevir
        Flutter'da QrImageView widget'ı bu string'i kullanacak
        """
        try:
            logger.debug(f"🔳 QR kod oluşturuluyor - URL: {payment_url}")
            
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
            logger.debug(f"✅ QR kod verisi oluşturuldu")
            return payment_url
            
        except Exception as e:
            logger.error(f"❌ QR kod oluşturma hatası: {str(e)}")
            # Hata durumunda da URL'yi döndür
            return payment_url

    def check_payment_status(self, transaction_id: str):
        """
        Checkout Form token'ı ile ödeme durumunu kontrol et - DEBUG VERSİYONU
        """
        try:
            logger.debug(f"🔍 Iyzico ödeme durumu sorgulanıyor: {transaction_id}")
            
            import iyzipay
            
            request_data = {
                'locale': 'tr',
                'conversationId': f'check-{transaction_id}',
                'token': transaction_id
            }
            
            logger.debug(f"🔄 Checkout Form retrieve çağrısı yapılıyor...")
            
            # Checkout Form durumunu sorgula
            checkout_form_result = iyzipay.CheckoutForm().retrieve(request_data, self.options)
            
            logger.debug(f"✅ Checkout Form retrieve response alındı")
            logger.debug(f"   - Response type: {type(checkout_form_result)}")
            
            if hasattr(checkout_form_result, 'status'):
                logger.debug(f"   - Status: {checkout_form_result.status}")
                
                if checkout_form_result.status == 'success':
                    payment_status = getattr(checkout_form_result, 'payment_status', 'UNKNOWN')
                    logger.debug(f"   - Payment Status: {payment_status}")
                    
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
                    logger.debug(f"✅ Ödeme durumu - Token: {transaction_id}, Status: {payment_status} -> {mapped_status}")
                    
                    return {"status": mapped_status}
                else:
                    error_message = getattr(checkout_form_result, 'error_message', 'Durum sorgulanamadı')
                    logger.warning(f"⚠️ Iyzico durum sorgulama hatası: {error_message}")
                    return {"status": "pending"}
            else:
                logger.warning(f"⚠️ Checkout Form retrieve response'da status bulunamadı")
                return {"status": "pending"}
                
        except ImportError as e:
            logger.error(f"❌ iyzipay kütüphanesi hatası: {e}")
            return {"status": "pending"}
        except Exception as e:
            logger.error(f"❌ Ödeme durumu sorgulama hatası: {str(e)}", exc_info=True)
            return {"status": "pending"}

    def _prepare_buyer_info(self, order: Order):
        """Alıcı bilgilerini Iyzico formatında hazırla - DEBUG"""
        logger.debug("👤 Buyer bilgileri hazırlanıyor...")
        
        buyer_info = {
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
        
        logger.debug(f"✅ Buyer: {buyer_info['name']} {buyer_info['surname']} - {buyer_info['email']}")
        return buyer_info

    def _prepare_address_info(self, order: Order, address_type: str):
        """Adres bilgilerini Iyzico formatında hazırla - DEBUG"""
        logger.debug(f"🏠 {address_type.title()} adresi hazırlanıyor...")
        
        address_info = {
            'contactName': order.customer_name or 'Müşteri',
            'city': 'İstanbul',
            'country': 'Turkey',
            'address': f'{order.business.name} - {address_type.title()} Address',
            'zipCode': '34000'
        }
        
        logger.debug(f"✅ {address_type.title()} Address: {address_info['address']}")
        return address_info

    def _prepare_basket_items(self, order: Order):
        """Sipariş öğelerini Iyzico formatına çevir - DEBUG"""
        logger.debug(f"🛒 Basket items hazırlanıyor - {order.order_items.count()} adet item...")
        
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
            
            item_price = (item.price * item.quantity).quantize(Decimal('0.01'))
            
            basket_item = {
                'id': f'item-{item.id}',
                'name': item_name[:255],  # Iyzico karakter sınırı
                'category1': category_name[:255],
                'category2': 'Restoran',
                'itemType': 'VIRTUAL',
                'price': str(item_price)
            }
            
            basket_items.append(basket_item)
            logger.debug(f"   + {basket_item['name']} - {basket_item['price']} TL")
        
        logger.debug(f"✅ {len(basket_items)} basket item hazırlandı")
        return basket_items