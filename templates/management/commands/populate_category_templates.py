# templates/management/commands/populate_category_templates.py

from django.core.management.base import BaseCommand
from templates.models import CategoryTemplate

class Command(BaseCommand):
    help = 'Hazır kategori şablonlarını veritabanına ekler.'

    def handle(self, *args, **options):
        templates = {
            'tr': [
                {'name': 'Yiyecekler', 'icon_name': 'restaurant'},
                {'name': 'İçecekler', 'icon_name': 'local_cafe'},
                {'name': 'Tatlılar', 'icon_name': 'cake'},
                {'name': 'Mezeler', 'icon_name': 'tapas'},
                {'name': 'Sıcak İçecekler', 'icon_name': 'coffee'},
                {'name': 'Soğuk İçecekler', 'icon_name': 'ac_unit'},
                {'name': 'Alkollü İçecekler', 'icon_name': 'local_bar'},
                {'name': 'Çorbalar', 'icon_name': 'soup_kitchen'},
                {'name': 'Salatalar', 'icon_name': 'eco'},
            ],
            'en': [
                {'name': 'Food', 'icon_name': 'restaurant'},
                {'name': 'Drinks', 'icon_name': 'local_cafe'},
                {'name': 'Desserts', 'icon_name': 'cake'},
                {'name': 'Appetizers', 'icon_name': 'tapas'},
                {'name': 'Hot Drinks', 'icon_name': 'coffee'},
                {'name': 'Cold Drinks', 'icon_name': 'ac_unit'},
                {'name': 'Alcoholic Drinks', 'icon_name': 'local_bar'},
                {'name': 'Soups', 'icon_name': 'soup_kitchen'},
                {'name': 'Salads', 'icon_name': 'eco'},
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