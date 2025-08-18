# core/management/commands/create_missing_stocks.py

from django.core.management.base import BaseCommand
from django.db.models import Count
from core.models import MenuItemVariant, Stock
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Finds all MenuItemVariants that do not have a corresponding Stock record and creates one for them with a quantity of 0.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Missing stock records are being checked...'))

        # Stok kaydı olmayan tüm varyantları bul
        variants_without_stock = MenuItemVariant.objects.filter(stock__isnull=True)
        
        count = variants_without_stock.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('All variants have a stock record. No action needed.'))
            return

        self.stdout.write(self.style.WARNING(f'Found {count} variants without a stock record. Creating them now...'))

        created_count = 0
        for variant in variants_without_stock:
            # GÜNCELLEME: get_or_create metoduna yeni alanlar için varsayılan değerler eklendi
            stock, created = Stock.objects.get_or_create(
                variant=variant,
                defaults={
                    'quantity': 0,
                    'track_stock': True,      # Varsayılan olarak stok takibi aktif olsun
                    'alert_threshold': None,  # Varsayılan olarak uyarı eşiği olmasın
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f"  - Created stock record for variant: '{variant.name}' (ID: {variant.id})")
        
        self.stdout.write(self.style.SUCCESS(f'Process finished. Successfully created {created_count} new stock records.'))