# subscriptions/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Plan, Subscription
from core.models import Business
from core.token import CustomTokenObtainPairSerializer 
from .services import SubscriptionService

logger = logging.getLogger(__name__)

class VerifyPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Flutter'dan gelen satın alma fişini doğrular, aboneliği aktive eder ve
        güncellenmiş kullanıcı bilgilerini içeren yeni bir token payload'ı döndürür.
        """
        provider = request.data.get('provider')
        token = request.data.get('token')
        product_id = request.data.get('product_id')

        if not all([provider, token, product_id]):
            return Response({'detail': 'Eksik parametreler.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            business = request.user.owned_business
        except Business.DoesNotExist:
            return Response({'detail': 'Bu kullanıcıya ait bir işletme bulunamadı.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            plan = Plan.objects.get(
                Q(google_product_id_monthly=product_id) | Q(google_product_id_yearly=product_id) |
                Q(apple_product_id_monthly=product_id) | Q(apple_product_id_yearly=product_id),
                is_active=True
            )
        except Plan.DoesNotExist:
            return Response({'detail': 'Geçersiz veya aktif olmayan ürün IDsi.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            is_valid, expiry_date = SubscriptionService.verify_purchase(provider, token, product_id)
            
            if is_valid and expiry_date:
                subscription, created = Subscription.objects.update_or_create(
                    business=business,
                    defaults={
                        'plan': plan,
                        'status': 'active',
                        'provider': provider,
                        'provider_subscription_id': f"sub_{token[:20]}",
                        'expires_at': expiry_date,
                    }
                )
                
                # +++++++++++++++++++ KESİN ÇÖZÜM BURADA +++++++++++++++++++
                # 1. Mevcut kullanıcı için güncel bilgileri içeren yeni bir Refresh Token nesnesi oluştur.
                refresh_token_object = CustomTokenObtainPairSerializer.get_token(request.user)

                # 2. Yanıt için boş bir sözlük oluştur.
                response_data = {
                    'refresh': str(refresh_token_object),
                    'access': str(refresh_token_object.access_token),
                }

                # 3. Token nesnesinin içindeki '.payload' sözlüğünü yanıta ekle.
                #    Hatanın kaynağı olan `data.update(refresh)` yerine bu KESİNLİKLE çalışır.
                response_data.update(refresh_token_object.payload)
                
                # 4. Bu güncel veriyi Flutter'a geri gönder.
                return Response(response_data, status=status.HTTP_200_OK)
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++

            else:
                return Response({'detail': 'Satın alma doğrulanamadı veya geçersiz.'}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            # Hata loglama
            logger.error(f"ABONELİK DOĞRULAMA HATASI: {e}", exc_info=True)
            return Response({'detail': f'Doğrulama sırasında bir hata oluştu: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)