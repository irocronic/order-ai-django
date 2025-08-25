# core/management/commands/populate_notification_settings.py

from django.core.management.base import BaseCommand
from core.models import NOTIFICATION_EVENT_TYPES, NotificationSetting

class Command(BaseCommand):
    help = 'NOTIFICATION_EVENT_TYPES listesindeki tüm olaylar için NotificationSetting tablosunu doldurur.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Bildirim ayarları dolduruluyor...'))
        created_count = 0
        
        for event_key, event_description in NOTIFICATION_EVENT_TYPES:
            setting, created = NotificationSetting.objects.get_or_create(
                event_type=event_key,
                defaults={
                    'is_active': True,  # Varsayılan olarak hepsi aktif
                    'description': event_description
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f"  - '{event_key}' için ayar oluşturuldu.")
        
        self.stdout.write(self.style.SUCCESS(f'İşlem tamamlandı. {created_count} yeni ayar oluşturuldu.'))