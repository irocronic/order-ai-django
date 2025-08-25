# core/signals/business_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import time

# GÜNCELLENMİŞ: CustomUser ve Business modellerini import ediyoruz
from ..models import Business, Shift, CustomUser

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
            color='#FFC107'
        )
        print(f"SİNYAL TETİKLENDİ: '{instance.name}' işletmesi için varsayılan vardiya şablonu oluşturuldu.")

@receiver(post_save, sender=CustomUser)
def deactivate_staff_on_business_owner_deactivation(sender, instance, **kwargs):
    """
    Bir kullanıcı güncellendiğinde tetiklenir.
    Eğer güncellenen kullanıcı bir işletme sahibiyse ve hesabı pasif hale getirildiyse,
    o işletmeye bağlı tüm personelin hesaplarını da pasif hale getirir.
    """
    update_fields = kwargs.get('update_fields')
    if update_fields and 'is_active' in update_fields and instance.user_type == 'business_owner':
        if not instance.is_active:
            try:
                business = instance.owned_business
                if business:
                    staff_to_deactivate = business.staff_members.filter(is_active=True)
                    deactivated_count = staff_to_deactivate.update(is_active=False)
                    if deactivated_count > 0:
                        print(f"SİNYAL TETİKLENDİ: '{business.name}' işletmesi pasifleştirildiği için {deactivated_count} personelin hesabı da pasifleştirildi.")
            except Business.DoesNotExist:
                pass