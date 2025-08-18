# subscriptions/management/commands/check_expired_trials.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Business

class Command(BaseCommand):
    help = 'Deneme süresi dolan ve abonelik başlatmayan işletmeleri pasif hale getirir.'

    def handle(self, *args, **options):
        now = timezone.now()
        self.stdout.write(f'[{now}] Deneme süresi dolan hesaplar kontrol ediliyor...')

        expired_businesses = Business.objects.filter(
            subscription_status='trial',
            trial_ends_at__lt=now
        )

        deactivated_count = 0
        for business in expired_businesses:
            business.subscription_status = 'inactive'
            business.save()
            deactivated_count += 1
            self.stdout.write(self.style.WARNING(
                f"İşletme '{business.name}' (ID: {business.id}) deneme süresi dolduğu için pasif hale getirildi."
            ))

        if deactivated_count > 0:
            self.stdout.write(self.style.SUCCESS(
                f'Toplam {deactivated_count} işletmenin üyeliği pasifleştirildi.'
            ))
        else:
            self.stdout.write('Süresi dolan deneme üyeliği bulunamadı.')