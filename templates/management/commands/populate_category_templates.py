# templates/management/commands/populate_category_templates.py

from django.core.management.base import BaseCommand
from templates.models import CategoryTemplate

class Command(BaseCommand):
    help = 'Hazır kategori şablonlarını veritabanına ekler.'

    def handle(self, *args, **options):
        # İSİMLER GÜNCELLENDİ VE EKSİK OLAN EKLENDİ
        templates = {
            'tr': [
                {'name': 'Ana Yemekler', 'icon_name': 'restaurant'},
                {'name': 'Çorbalar', 'icon_name': 'soup_kitchen'},
                {'name': 'Mezeler & Aperatifler', 'icon_name': 'tapas'},
                {'name': 'Salatalar', 'icon_name': 'eco'},
                {'name': 'Atıştırmalıklar & Fast Food', 'icon_name': 'fastfood'},
                {'name': 'Tatlılar', 'icon_name': 'cake'},
                {'name': 'Sıcak İçecekler', 'icon_name': 'coffee'},
                {'name': 'Soğuk İçecekler', 'icon_name': 'ac_unit'},
                {'name': 'Alkollü İçecekler', 'icon_name': 'local_bar'},
            ],
            'en': [
                # İngilizce karşılıkları da buraya eklenebilir.
                {'name': 'Main Courses', 'icon_name': 'restaurant'},
                {'name': 'Soups', 'icon_name': 'soup_kitchen'},
                {'name': 'Appetizers & Mezes', 'icon_name': 'tapas'},
                {'name': 'Salads', 'icon_name': 'eco'},
                {'name': 'Snacks & Fast Food', 'icon_name': 'fastfood'},
                {'name': 'Desserts', 'icon_name': 'cake'},
                {'name': 'Hot Drinks', 'icon_name': 'coffee'},
                {'name': 'Cold Drinks', 'icon_name': 'ac_unit'},
                {'name': 'Alcoholic Drinks', 'icon_name': 'local_bar'},
            ]
        }

        created_count = 0
        for lang, tpl_list in templates.items():
            for tpl in tpl_list:
                obj, created = CategoryTemplate.objects.get_or_create(
                    language=lang,
                    name=tpl['name'],
                    defaults={'icon_name': tpl['icon_name']}
                )
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"'{tpl['name']}' ({lang}) şablonu oluşturuldu."))
        
        self.stdout.write(self.style.SUCCESS(f'İşlem tamamlandı. {created_count} yeni şablon eklendi.'))