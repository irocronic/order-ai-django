import os
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from templates.models import CategoryTemplate, MenuItemTemplate, VariantTemplate

class Command(BaseCommand):
    help = 'Populates all templates (categories, menu items, variants) from language-specific JSON files.'

    def handle(self, *args, **options):
        # templates/data klasörünün yolunu belirle
        data_dir = os.path.join(settings.BASE_DIR, 'templates', 'data')
        
        if not os.path.exists(data_dir):
            self.stdout.write(self.style.ERROR(f"Data directory not found at: {data_dir}"))
            return

        self.stdout.write(self.style.NOTICE('Starting to populate all templates...'))
        
        # data klasöründeki tüm .json dosyalarını işle
        for filename in os.listdir(data_dir):
            if filename.endswith('.json'):
                language_code = filename.split('.')[0]
                self.stdout.write(self.style.HTTP_INFO(f"Processing templates for language: '{language_code}'"))
                
                file_path = os.path.join(data_dir, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                categories_data = data.get('categories', [])
                
                for cat_data in categories_data:
                    # Kategori Şablonunu oluştur/güncelle
                    category_template, created_cat = CategoryTemplate.objects.get_or_create(
                        name=cat_data['name'],
                        language=language_code,
                        defaults={'icon_name': cat_data.get('icon', 'restaurant')}
                    )
                    if created_cat:
                        self.stdout.write(f"  - Created Category: '{category_template.name}' ({language_code})")

                    # Menü Öğesi Şablonlarını oluştur/güncelle
                    for item_data in cat_data.get('menu_items', []):
                        _, created_item = MenuItemTemplate.objects.get_or_create(
                            category_template=category_template,
                            name=item_data['name'],
                            language=language_code
                        )
                        if created_item:
                            self.stdout.write(f"    - Created Menu Item: '{item_data['name']}'")

                    # Varyant Şablonlarını oluştur/güncelle
                    for var_data in cat_data.get('variants', []):
                        _, created_var = VariantTemplate.objects.get_or_create(
                            category_template=category_template,
                            name=var_data['name'],
                            language=language_code,
                            defaults={
                                'price_multiplier': var_data.get('multiplier', 1.0),
                                'icon_name': var_data.get('icon', 'label_outline'),
                                'display_order': var_data.get('order', 0)
                            }
                        )
                        if created_var:
                            self.stdout.write(f"    - Created Variant: '{var_data['name']}'")

        self.stdout.write(self.style.SUCCESS('All templates populated successfully.'))