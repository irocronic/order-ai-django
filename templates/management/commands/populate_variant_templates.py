# templates/management/commands/populate_variant_templates.py

from django.core.management.base import BaseCommand
from templates.models import CategoryTemplate, VariantTemplate

class Command(BaseCommand):
    help = 'Hazır varyant şablonlarını veritabanına ekler.'

    def handle(self, *args, **options):
        # Varyant şablonları kategorilere göre
        variant_data = {
            'Ana Yemekler': [
                {'name': 'Küçük Porsiyon', 'price_multiplier': 0.7, 'icon_name': 'restaurant_outlined', 'order': 1},
                {'name': 'Orta Porsiyon', 'price_multiplier': 1.0, 'icon_name': 'restaurant', 'order': 2},
                {'name': 'Büyük Porsiyon', 'price_multiplier': 1.3, 'icon_name': 'dinner_dining', 'order': 3},
                {'name': 'XL Porsiyon', 'price_multiplier': 1.6, 'icon_name': 'dining', 'order': 4},
                {'name': 'Acısız', 'price_multiplier': 1.0, 'icon_name': 'mood', 'order': 5},
                {'name': 'Az Acı', 'price_multiplier': 1.0, 'icon_name': 'whatshot_outlined', 'order': 6},
                {'name': 'Orta Acı', 'price_multiplier': 1.0, 'icon_name': 'whatshot', 'order': 7},
                {'name': 'Çok Acı', 'price_multiplier': 1.0, 'icon_name': 'local_fire_department', 'order': 8},
            ],
            'Çorbalar': [
                {'name': 'Küçük Kase', 'price_multiplier': 0.8, 'icon_name': 'soup_kitchen_outlined', 'order': 1},
                {'name': 'Büyük Kase', 'price_multiplier': 1.2, 'icon_name': 'soup_kitchen', 'order': 2},
                {'name': 'Acısız', 'price_multiplier': 1.0, 'icon_name': 'mood', 'order': 3},
                {'name': 'Acılı', 'price_multiplier': 1.0, 'icon_name': 'whatshot', 'order': 4},
            ],
            'Tatlılar': [
                {'name': 'Tek Kişilik', 'price_multiplier': 1.0, 'icon_name': 'cake_outlined', 'order': 1},
                {'name': 'İki Kişilik', 'price_multiplier': 1.8, 'icon_name': 'cake', 'order': 2},
                {'name': 'Şekersiz', 'price_multiplier': 1.0, 'icon_name': 'no_food', 'order': 3},
                {'name': 'Extra Şekerli', 'price_multiplier': 1.1, 'icon_name': 'add_circle', 'order': 4},
            ],
            'Sıcak İçecekler': [
                {'name': 'Küçük', 'price_multiplier': 0.8, 'icon_name': 'local_cafe_outlined', 'order': 1},
                {'name': 'Orta', 'price_multiplier': 1.0, 'icon_name': 'local_cafe', 'order': 2},
                {'name': 'Büyük', 'price_multiplier': 1.3, 'icon_name': 'coffee', 'order': 3},
                {'name': 'Sütsüz', 'price_multiplier': 0.9, 'icon_name': 'no_drinks', 'order': 4},
                {'name': 'Az Süt', 'price_multiplier': 1.0, 'icon_name': 'opacity', 'order': 5},
                {'name': 'Bol Süt', 'price_multiplier': 1.1, 'icon_name': 'water_drop', 'order': 6},
                {'name': 'Şekersiz', 'price_multiplier': 1.0, 'icon_name': 'heart_broken', 'order': 7},
                {'name': 'Az Şeker', 'price_multiplier': 1.0, 'icon_name': 'favorite_border', 'order': 8},
                {'name': 'Şekerli', 'price_multiplier': 1.0, 'icon_name': 'favorite', 'order': 9},
            ],
            'Soğuk İçecekler': [
                {'name': '20cl', 'price_multiplier': 0.7, 'icon_name': 'local_drink_outlined', 'order': 1},
                {'name': '33cl', 'price_multiplier': 1.0, 'icon_name': 'local_drink', 'order': 2},
                {'name': '50cl', 'price_multiplier': 1.4, 'icon_name': 'sports_bar', 'order': 3},
                {'name': '1L', 'price_multiplier': 2.0, 'icon_name': 'liquor', 'order': 4},
                {'name': 'Buzlu', 'price_multiplier': 1.0, 'icon_name': 'ac_unit', 'order': 5},
                {'name': 'Buzsuz', 'price_multiplier': 1.0, 'icon_name': 'block', 'order': 6},
            ],
            'Alkollü İçecekler': [
                {'name': 'Tek', 'price_multiplier': 1.0, 'icon_name': 'local_bar_outlined', 'order': 1},
                {'name': 'Double', 'price_multiplier': 1.8, 'icon_name': 'local_bar', 'order': 2},
                {'name': 'Buzlu', 'price_multiplier': 1.0, 'icon_name': 'ac_unit', 'order': 3},
                {'name': 'Neat', 'price_multiplier': 1.0, 'icon_name': 'wine_bar', 'order': 4},
            ],
            'Atıştırmalıklar & Fast Food': [
                {'name': 'Küçük', 'price_multiplier': 0.8, 'icon_name': 'fastfood_outlined', 'order': 1},
                {'name': 'Orta', 'price_multiplier': 1.0, 'icon_name': 'fastfood', 'order': 2},
                {'name': 'Büyük', 'price_multiplier': 1.3, 'icon_name': 'lunch_dining', 'order': 3},
                {'name': 'Menü', 'price_multiplier': 1.5, 'icon_name': 'dining', 'order': 4},
                {'name': 'Extra Peynir', 'price_multiplier': 1.1, 'icon_name': 'add_circle', 'order': 5},
                {'name': 'Extra Patates', 'price_multiplier': 1.1, 'icon_name': 'add', 'order': 6},
            ],
        }
        
        created_count = 0
        skipped_count = 0

        for category_name, variants in variant_data.items():
            try:
                category_template = CategoryTemplate.objects.get(name=category_name, language='tr')
                for variant_data_item in variants:
                    _, created = VariantTemplate.objects.get_or_create(
                        category_template=category_template,
                        name=variant_data_item['name'],
                        language='tr',
                        defaults={
                            'price_multiplier': variant_data_item['price_multiplier'],
                            'icon_name': variant_data_item['icon_name'],
                            'display_order': variant_data_item['order'],
                        }
                    )
                    if created:
                        created_count += 1
                self.stdout.write(self.style.SUCCESS(f"'{category_name}' kategorisi için {len(variants)} varyant şablonu işlendi."))
            except CategoryTemplate.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"UYARI: '{category_name}' isimli kategori şablonu bulunamadı. Bu kategori atlanıyor."))
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(f'İşlem tamamlandı. {created_count} yeni varyant şablonu eklendi. {skipped_count} kategori atlandı.'))