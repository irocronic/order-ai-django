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
import json

logger = logging.getLogger(__name__)

class IyzicoPaymentService(BasePaymentService):
    def __init__(self, business: Business):
        super().__init__(business)
        # Debug bilgileri
        logger.info(f"=== IYZICO SERVICE DEBUG ===")
        logger.info(f"Business ID: {business.id}")
        logger.info(f"Business Name: {business.name}")
        
        # CRITICAL DEBUG: Encrypted field'ları decrypt ederek gerçek değerlerini görelim
        logger.info(f"=== ENCRYPTION DEBUG ===")
        try:
            # Veritabanından taze veri çek
            fresh_business = Business.objects.get(id=business.id)
            
            # Encrypted field'ların decrypt edilmiş değerlerini logla
            decrypted_api_key = fresh_business.payment_api_key
            decrypted_secret_key = fresh_business.payment_secret_key
            
            logger.info(f"🔓 Decrypted API Key: '{decrypted_api_key}'")
            logger.info(f"🔓 Decrypted Secret Key: '{decrypted_secret_key}'")
            logger.info(f"🔓 API Key uzunluğu: {len(decrypted_api_key) if decrypted_api_key else 0}")
            logger.info(f"🔓 Secret Key uzunluğu: {len(decrypted_secret_key) if decrypted_secret_key else 0}")
            logger.info(f"🔓 API Key boş mu: {not bool(decrypted_api_key and decrypted_api_key.strip())}")
            logger.info(f"🔓 Secret Key boş mu: {not bool(decrypted_secret_key and decrypted_secret_key.strip())}")
            
            # self.api_key ve self.secret_key değerlerini de kontrol et
            logger.info(f"🔧 self.api_key: '{self.api_key}'")
            logger.info(f"🔧 self.secret_key: '{self.secret_key}'")
            logger.info(f"🔧 self.api_key == decrypted_api_key: {self.api_key == decrypted_api_key}")
            logger.info(f"🔧 self.secret_key == decrypted_secret_key: {self.secret_key == decrypted_secret_key}")
            
        except Exception as debug_error:
            logger.error(f"❌ Encryption debug hatası: {debug_error}")
        
        # Iyzico SDK'sını import et ve yapılandır
        self._setup_iyzico_sdk()

    def _setup_iyzico_sdk(self):
        """Iyzico SDK'sını yapılandır"""
        try:
            import iyzipay
            logger.info("✅ iyzipay modülü başarıyla import edildi")
            
            # API Key kontrolü
            logger.info(f"API Key var mı: {'✅ Evet' if self.api_key else '❌ Hayır'}")
            logger.info(f"Secret Key var mı: {'✅ Evet' if self.secret_key else '❌ Hayır'}")
            
            if not self.api_key or not self.secret_key:
                logger.error("❌ API Key veya Secret Key boş!")
                raise Exception("API Key veya Secret Key boş")
                
            # Options dictionary olarak oluştur
            self.options = {
                'api_key': self.api_key,
                'secret_key': self.secret_key,
            }
            
            # DÜZELTME: API anahtarına göre base URL belirle
            if self.api_key.startswith('sandbox-'):
                self.options['base_url'] = "sandbox-api.iyzipay.com"  # Sandbox için
                logger.info("🔧 Iyzico SDK Sandbox ortamı için yapılandırıldı")
            else:
                self.options['base_url'] = "api.iyzipay.com"  # Production için  
                logger.info("🔧 Iyzico SDK Production ortamı için yapılandırıldı")
                    
            logger.info(f"Base URL: {self.options['base_url']}")
            logger.info(f"Final options: {{'api_key': '***', 'secret_key': '***', 'base_url': '{self.options['base_url']}'}}")
                    
        except ImportError as e:
            logger.error(f"❌ iyzipay kütüphanesi bulunamadı: {str(e)}")
            raise ImportError("iyzipay kütüphanesi yüklenmelidir")
        except Exception as e:
            logger.error(f"❌ Iyzico SDK yapılandırma hatası: {str(e)}")
            raise

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
            
            logger.info(f"🚀 Iyzico QR ödeme oluşturma başlıyor: Order #{order.id}")
            
            # CRITICAL DEBUG: SDK çağrısından hemen önce anahtarları tekrar kontrol et
            logger.info(f"=== SDK CALL DEBUG ===")
            logger.info(f"API Key boş mu: {not bool(self.api_key and self.api_key.strip())}")
            logger.info(f"Secret Key boş mu: {not bool(self.secret_key and self.secret_key.strip())}")
            
            if not self.api_key or not self.api_key.strip():
                logger.error("❌ API Key boş! SDK çağrısı yapılamaz.")
                raise Exception("API Key boş - encrypted field decrypt edilememiş olabilir")
                
            if not self.secret_key or not self.secret_key.strip():
                logger.error("❌ Secret Key boş! SDK çağrısı yapılamaz.")
                raise Exception("Secret Key boş - encrypted field decrypt edilememiş olabilir")
            
            # Debug: Payment provider config kontrol
            try:
                payment_config = getattr(self.business, 'payment_provider_config', None)
                logger.info(f"Payment Provider Config: {'✅ Var' if payment_config else '❌ Yok'}")
                if payment_config:
                    logger.info(f"Config ID: {payment_config.id}")
            except Exception as config_error:
                logger.warning(f"⚠️ Payment config kontrol hatası: {config_error}")
            
            # 1. Checkout Form için request hazırla
            conversation_id = f'order-{order.id}-{str(order.uuid)[:8]}'
            logger.info(f"Conversation ID: {conversation_id}")
            
            # Price hesaplamaları debug
            price = str(order.grand_total.quantize(Decimal('0.01')))
            logger.info(f"💰 Toplam tutar: {price} {order.business.currency_code or 'TRY'}")
            
            # HATA DÜZELTMESİ: Basket items toplam fiyat kontrolü
            basket_items = self._prepare_basket_items(order)
            basket_total = sum(Decimal(item['price']) for item in basket_items)
            
            logger.info(f"💰 Order Grand Total: {order.grand_total}")
            logger.info(f"💰 Basket Items Total: {basket_total}")
            logger.info(f"💰 Fark: {order.grand_total - basket_total}")
            
            # Eğer fark varsa düzelt
            if abs(order.grand_total - basket_total) > Decimal('0.01'):
                logger.warning(f"⚠️ Toplam tutarlar eşleşmiyor! Order: {order.grand_total}, Basket: {basket_total}")
                # Son item'ın fiyatını ayarla
                if basket_items:
                    difference = order.grand_total - basket_total
                    last_item_price = Decimal(basket_items[-1]['price']) + difference
                    basket_items[-1]['price'] = str(last_item_price.quantize(Decimal('0.01')))
                    logger.info(f"✅ Son item fiyatı düzeltildi: {basket_items[-1]['price']}")
            
            request_data = {
                'locale': 'tr',
                'conversationId': conversation_id,
                'price': price,
                'paidPrice': price,
                'currency': order.business.currency_code or 'TRY',
                'basketId': str(order.id),
                'paymentGroup': 'PRODUCT',
                'callbackUrl': f'{settings.BASE_URL}/api/iyzico/callback/',
                'enabledInstallments': ["1"],  # STRING ARRAY olarak gönder
                'buyer': self._prepare_buyer_info(order),
                'shippingAddress': self._prepare_address_info(order, 'shipping'),
                'billingAddress': self._prepare_address_info(order, 'billing'),
                'basketItems': basket_items,
            }
            
            logger.info("📦 Request data hazırlandı")
            logger.info(f"Basket items sayısı: {len(request_data['basketItems'])}")
            
            # Final validation
            final_basket_total = sum(Decimal(item['price']) for item in request_data['basketItems'])
            logger.info(f"💰 Final validation - Order: {price}, Basket: {final_basket_total}")
            
            # 2. Checkout Form initialize et
            logger.info("🔄 Checkout Form initialize ediliyor...")
            logger.info(f"Options: {{'api_key': '***', 'secret_key': '***', 'base_url': '{self.options.get('base_url', 'N/A')}'}}")
            
            checkout_form_initialize = iyzipay.CheckoutFormInitialize().create(request_data, self.options)
            
            logger.info(f"📥 API Response alındı")
            
            # Response kontrolü - JSON parse et
            if hasattr(checkout_form_initialize, 'read'):
                # HTTP Response objesi ise
                response_body = checkout_form_initialize.read()
                logger.info(f"Raw response body: {response_body}")
                
                try:
                    response_data = json.loads(response_body.decode('utf-8'))
                    logger.info(f"Parsed response: {response_data}")
                    
                    if response_data.get('status') == 'success':
                        payment_url = response_data.get('paymentPageUrl')
                        transaction_token = response_data.get('token')
                        
                        logger.info(f"✅ Checkout Form başarılı! Token: {transaction_token}")
                        
                        # 3. Payment URL'ini QR kod'una çevir
                        qr_data_string = self._generate_qr_code_string(payment_url)
                        
                        return {
                            "qr_data": qr_data_string,
                            "transaction_id": transaction_token
                        }
                    else:
                        error_code = response_data.get('errorCode', 'UNKNOWN')
                        error_message = response_data.get('errorMessage', 'Bilinmeyen hata')
                        logger.error(f"❌ Iyzico API Error [{error_code}]: {error_message}")
                        raise Exception(f"Iyzico API Error [{error_code}]: {error_message}")
                        
                except json.JSONDecodeError as json_error:
                    logger.error(f"❌ JSON parse hatası: {json_error}")
                    logger.error(f"Raw response: {response_body}")
                    raise Exception(f"API response parse hatası: {json_error}")
            else:
                # Normal response objesi
                if hasattr(checkout_form_initialize, 'status') and checkout_form_initialize.status == 'success':
                    payment_url = checkout_form_initialize.payment_page_url
                    transaction_token = checkout_form_initialize.token
                    
                    logger.info(f"✅ Checkout Form başarılı! Token: {transaction_token}")
                    
                    # 3. Payment URL'ini QR kod'una çevir
                    qr_data_string = self._generate_qr_code_string(payment_url)
                    
                    return {
                        "qr_data": qr_data_string,
                        "transaction_id": transaction_token
                    }
                else:
                    error_message = getattr(checkout_form_initialize, 'error_message', 'Checkout form oluşturulamadı')
                    logger.error(f"❌ Iyzico Checkout Form hatası: {error_message}")
                    raise Exception(f"Iyzico Checkout Form hatası: {error_message}")
                
        except ImportError as import_error:
            logger.error(f"❌ iyzipay kütüphanesi bulunamadı: {import_error}")
            raise Exception("iyzipay kütüphanesi yüklenmemiş")
        except Exception as e:
            logger.error(f"❌ QR ödeme oluşturma hatası: {str(e)}", exc_info=True)
            raise Exception(f"QR ödeme oluşturma hatası: {str(e)}")

    def _generate_qr_code_string(self, payment_url):
        """
        Ödeme URL'ini QR kod string'ine çevir
        Flutter'da QrImageView widget'ı bu string'i kullanacak
        """
        try:
            logger.info(f"🔗 QR kod oluşturuluyor: {payment_url}")
            
            # Flutter için sadece URL string'ini döndür
            # Flutter'daki QrImageView widget'ı bu URL'yi kullanarak QR kodu oluşturacak
            logger.info("✅ QR kod verisi hazır")
            return payment_url
            
        except Exception as e:
            logger.error(f"❌ QR kod oluşturma hatası: {str(e)}")
            # Hata durumunda da URL'yi döndür
            return payment_url

    def check_payment_status(self, transaction_id: str):
        """
        Checkout Form token'ı ile ödeme durumunu kontrol et
        """
        try:
            import iyzipay
            
            logger.debug(f"🔍 Iyzico ödeme durumu sorgulanıyor: {transaction_id}")
            
            request_data = {
                'locale': 'tr',
                'conversationId': f'check-{transaction_id}',
                'token': transaction_id
            }
            
            # Checkout Form durumunu sorgula
            checkout_form_result = iyzipay.CheckoutForm().retrieve(request_data, self.options)
            
            if hasattr(checkout_form_result, 'status') and checkout_form_result.status == 'success':
                payment_status = checkout_form_result.payment_status
                
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
                
        except ImportError:
            logger.error("❌ iyzipay kütüphanesi bulunamadı")
            return {"status": "pending"}
        except Exception as e:
            logger.error(f"❌ Ödeme durumu sorgulama hatası: {str(e)}", exc_info=True)
            return {"status": "pending"}

    def _prepare_buyer_info(self, order: Order):
        """Alıcı bilgilerini Iyzico formatında hazırla"""
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
        
        logger.debug(f"👤 Buyer info hazırlandı: {buyer_info['name']} - {buyer_info['email']}")
        return buyer_info

    def _prepare_address_info(self, order: Order, address_type: str):
        """Adres bilgilerini Iyzico formatında hazırla"""
        address_info = {
            'contactName': order.customer_name or 'Müşteri',
            'city': 'İstanbul',
            'country': 'Turkey',
            'address': f'{order.business.name} - {address_type.title()} Address',
            'zipCode': '34000'
        }
        
        logger.debug(f"📍 Address info hazırlandı ({address_type}): {address_info['contactName']}")
        return address_info

    def _prepare_basket_items(self, order: Order):
        """Sipariş öğelerini Iyzico formatına çevir"""
        basket_items = []
        
        logger.info(f"🛒 Basket items hazırlanıyor...")
        
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
            
            item_price = str((item.price * item.quantity).quantize(Decimal('0.01')))
            
            basket_item = {
                'id': f'item-{item.id}',
                'name': item_name[:255],  # Iyzico karakter sınırı
                'category1': category_name[:255],
                'category2': 'Restoran',
                'itemType': 'VIRTUAL',
                'price': item_price
            }
            
            basket_items.append(basket_item)
            logger.debug(f"  📦 Item: {item_name} - {item_price} TL")
        
        logger.info(f"✅ {len(basket_items)} basket item hazırlandı")
        return basket_items