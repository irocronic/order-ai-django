# subscriptions/services.py

from datetime import datetime, timezone as dt_timezone
from django.utils import timezone
from django.conf import settings

# Gerekli Google kütüphaneleri
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Business importu artık bu dosyada gerekli değil, çünkü model güncelleme
# işlemi views.py dosyasına taşındı.
# from core.models import Business


class SubscriptionService:
    """
    Uygulama mağazaları (Google Play, Apple App Store) ile iletişim kurarak
    satın alma işlemlerini doğrulayan servis.
    """
    @staticmethod
    def verify_purchase(provider, token, product_id):
        """Doğrulama isteğini doğru platforma yönlendirir."""
        if provider == "google_play":
            return SubscriptionService.verify_google_play_purchase(token, product_id)
        elif provider == "apple_app_store":
            return SubscriptionService.verify_app_store_purchase(token, product_id)
        else:
            raise ValueError("Desteklenmeyen sağlayıcı.")

    @staticmethod
    def verify_google_play_purchase(purchase_token: str, product_id: str):
        """
        Google Play’den gelen bir satın alma jetonunu doğrular.
        Başarılı olursa (True, expiry_date), başarısız olursa (False, None) döner.
        """
        try:
            credentials = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=["https://www.googleapis.com/auth/androidpublisher"],
            )

            android_publisher = build(
                "androidpublisher",
                "v3",
                credentials=credentials,
                cache_discovery=False,
            )

            purchase = (
                android_publisher.purchases()
                .subscriptions()
                .get(
                    packageName=settings.ANDROID_PACKAGE_NAME,
                    subscriptionId=product_id,
                    token=purchase_token,
                )
                .execute()
            )

            if purchase and purchase.get("expiryTimeMillis"):
                expiry_ms = int(purchase["expiryTimeMillis"])
                expiry_date_utc = datetime.fromtimestamp(expiry_ms / 1000, tz=dt_timezone.utc)

                if expiry_date_utc > timezone.now():
                    print(f"GOOGLE PLAY DOĞRULAMA BAŞARILI: Bitiş Tarihi (UTC): {expiry_date_utc}")
                    return True, expiry_date_utc

            print("GOOGLE PLAY DOĞRULAMA BAŞARISIZ – abonelik geçersiz/süresi dolmuş")
            return False, None

        except HttpError as e:
            print(f"GOOGLE PLAY API HATASI (HttpError): {e}")
            raise e
        except Exception as e:
            print(f"GENEL DOĞRULAMA HATASI: {e}")
            raise e

    @staticmethod
    def verify_app_store_purchase(receipt_data: str, product_id: str):
        """
        Apple App Store'dan gelen bir fişi doğrular (Bu kısım simülasyondur).
        """
        print(f"APP STORE DOĞRULAMA (simüle): product_id={product_id}")
        is_valid = True
        expiry_date = timezone.now() + timezone.timedelta(days=30)
        return is_valid, expiry_date