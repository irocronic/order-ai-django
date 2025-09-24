from django.core.management.base import BaseCommand
from core.models import Business

class Command(BaseCommand):
    help = 'Test payment settings encryption'

    def handle(self, *args, **options):
        business = Business.objects.get(id=1)
        
        # Test değerleri kaydet
        business.payment_provider = 'iyzico'
        business.payment_api_key = 'test_api_key_123'
        business.payment_secret_key = 'test_secret_key_456'
        business.save()
        
        print(f"Saved - Provider: {business.payment_provider}")
        print(f"Saved - API Key: {business.payment_api_key}")
        print(f"Saved - Secret Key: {business.payment_secret_key}")
        
        # Veritabanından tekrar oku
        business.refresh_from_db()
        
        print(f"After refresh - Provider: {business.payment_provider}")
        print(f"After refresh - API Key: {business.payment_api_key}")
        print(f"After refresh - Secret Key: {business.payment_secret_key}")