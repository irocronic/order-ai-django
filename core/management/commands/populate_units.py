# core/management/commands/populate_units.py

from django.core.management.base import BaseCommand
from core.models import UnitOfMeasure
import logging

# Konsol yerine log dosyasına yazdırmak için temel yapılandırma (isteğe bağlı)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Veritabanındaki UnitOfMeasure tablosunu yaygın olarak kullanılan
    ölçü birimleri ile doldurur. Mevcut birimleri tekrar eklemez.
    """
    help = 'Populates the database with common units of measure.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Ölçü birimleri veritabanına ekleniyor...'))

        units_to_add = [
            # Ağırlık Birimleri
            {'name': 'Gram', 'abbreviation': 'gr'},
            {'name': 'Kilogram', 'abbreviation': 'kg'},
            {'name': 'Miligram', 'abbreviation': 'mg'},
            
            # Hacim Birimleri
            {'name': 'Litre', 'abbreviation': 'lt'},
            {'name': 'Mililitre', 'abbreviation': 'ml'},
            {'name': 'Yemek Kaşığı', 'abbreviation': 'yk'},
            {'name': 'Çay Kaşığı', 'abbreviation': 'çk'},
            {'name': 'Su Bardağı', 'abbreviation': 'bardak'},

            # Sayısal Birimler
            {'name': 'Adet', 'abbreviation': 'ad'},
            {'name': 'Porsiyon', 'abbreviation': 'pors'},
            {'name': 'Paket', 'abbreviation': 'pkt'},
            {'name': 'Kutu', 'abbreviation': 'kutu'},
            {'name': 'Dilim', 'abbreviation': 'dilim'},
            {'name': 'Demet', 'abbreviation': 'demet'},
            
            # Uzunluk Birimleri (nadiren gerekebilir)
            {'name': 'Santimetre', 'abbreviation': 'cm'},
            {'name': 'Metre', 'abbreviation': 'm'},
        ]

        created_count = 0
        skipped_count = 0

        for unit_data in units_to_add:
            # get_or_create metodu, belirtilen birimin olup olmadığını kontrol eder.
            # Yoksa oluşturur, varsa mevcut olanı getirir. Duplikasyonu önler.
            obj, created = UnitOfMeasure.objects.get_or_create(
                name=unit_data['name'],
                defaults={'abbreviation': unit_data['abbreviation']}
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"-> '{obj.name} ({obj.abbreviation})' birimi başarıyla oluşturuldu."))
            else:
                skipped_count += 1
                # İsteğe bağlı: Mevcut birimler için de bilgi verebilirsiniz.
                # self.stdout.write(f"-> '{obj.name}' birimi zaten mevcut, atlanıyor.")

        self.stdout.write(self.style.SUCCESS(
            f'\nİşlem tamamlandı. {created_count} yeni ölçü birimi eklendi. {skipped_count} birim zaten mevcuttu.'
        ))