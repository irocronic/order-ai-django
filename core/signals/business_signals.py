# makarna_backend/core/signals/business_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import time

# Modelleri 'core' uygulamasından import ediyoruz
from ..models import Business, Shift

@receiver(post_save, sender=Business)
def create_default_shift_for_business(sender, instance, created, **kwargs):
    """
    Yeni bir Business (İşletme) oluşturulduğunda,
    o işletme için varsayılan bir vardiya şablonu oluşturur.
    """
    if created:
        Shift.objects.create(
            business=instance,
            name='09:00 - 18:00',
            start_time=time(9, 0),
            end_time=time(18, 0),
            color='#FFC107'  # Sarı renk için HEX kodu
        )
        print(f"SİNYAL TETİKLENDİ: '{instance.name}' işletmesi için varsayılan vardiya şablonu oluşturuldu.")