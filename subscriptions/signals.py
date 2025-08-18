# subscriptions/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

# Gerekli modelleri import ediyoruz
from core.models import Business
from .models import Subscription, Plan

@receiver(post_save, sender=Business)
def create_subscription_for_new_business(sender, instance, created, **kwargs):
    """
    Her yeni işletme için varsayılan bir deneme aboneliği oluşturur.
    En düşük seviye planı atar ve 7 günlük deneme süresi tanımlar.
    """
    if created:
        # En düşük seviyedeki (en az masa sayısına sahip) aktif planı bul.
        # Bu, "Temel" planın ID'sini bilmemize gerek kalmadan esnek bir yol sunar.
        default_plan = Plan.objects.filter(is_active=True).order_by('max_tables').first()
        
        # Yeni işletme için bir Abonelik (Subscription) nesnesi oluştur.
        Subscription.objects.create(
            business=instance,
            plan=default_plan,  # Bulunan varsayılan planı ata
            status='trial',     # Durumu 'deneme' olarak ayarla
            expires_at=timezone.now() + timedelta(days=7) # Bitiş tarihini 7 gün sonrası olarak ayarla
        )