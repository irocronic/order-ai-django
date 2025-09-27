# templates/management/commands/populate_variant_templates.py

from django.core.management.base import BaseCommand
from templates.models import CategoryTemplate, VariantTemplate

class Command(BaseCommand):
    help = 'Hazır varyant şablonlarını veritabanına ekler.'

    def handle(self, *args, **options):
        # Varyant şablonları kategorilere ve dillere göre
        variant_data = {
            # TÜRKÇE VARYANTLAR
            'tr': {
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
            },
            
            # İNGİLİZCE VARYANTLAR
            'en': {
                'Main Courses': [
                    {'name': 'Small Portion', 'price_multiplier': 0.7, 'icon_name': 'restaurant_outlined', 'order': 1},
                    {'name': 'Regular Portion', 'price_multiplier': 1.0, 'icon_name': 'restaurant', 'order': 2},
                    {'name': 'Large Portion', 'price_multiplier': 1.3, 'icon_name': 'dinner_dining', 'order': 3},
                    {'name': 'Extra Large', 'price_multiplier': 1.6, 'icon_name': 'dining', 'order': 4},
                    {'name': 'Mild', 'price_multiplier': 1.0, 'icon_name': 'mood', 'order': 5},
                    {'name': 'Medium Spicy', 'price_multiplier': 1.0, 'icon_name': 'whatshot_outlined', 'order': 6},
                    {'name': 'Hot', 'price_multiplier': 1.0, 'icon_name': 'whatshot', 'order': 7},
                    {'name': 'Extra Hot', 'price_multiplier': 1.0, 'icon_name': 'local_fire_department', 'order': 8},
                    {'name': 'Well Done', 'price_multiplier': 1.0, 'icon_name': 'local_fire_department', 'order': 9},
                    {'name': 'Medium', 'price_multiplier': 1.0, 'icon_name': 'restaurant', 'order': 10},
                    {'name': 'Rare', 'price_multiplier': 1.0, 'icon_name': 'favorite', 'order': 11},
                ],
                'Soups & Starters': [
                    {'name': 'Cup', 'price_multiplier': 0.8, 'icon_name': 'soup_kitchen_outlined', 'order': 1},
                    {'name': 'Bowl', 'price_multiplier': 1.2, 'icon_name': 'soup_kitchen', 'order': 2},
                    {'name': 'Mild', 'price_multiplier': 1.0, 'icon_name': 'mood', 'order': 3},
                    {'name': 'Spicy', 'price_multiplier': 1.0, 'icon_name': 'whatshot', 'order': 4},
                    {'name': 'With Bread', 'price_multiplier': 1.1, 'icon_name': 'breakfast_dining', 'order': 5},
                ],
                'Desserts & Sweets': [
                    {'name': 'Single Serving', 'price_multiplier': 1.0, 'icon_name': 'cake_outlined', 'order': 1},
                    {'name': 'Sharing Size', 'price_multiplier': 1.8, 'icon_name': 'cake', 'order': 2},
                    {'name': 'Sugar Free', 'price_multiplier': 1.0, 'icon_name': 'no_food', 'order': 3},
                    {'name': 'Extra Sweet', 'price_multiplier': 1.1, 'icon_name': 'add_circle', 'order': 4},
                    {'name': 'With Ice Cream', 'price_multiplier': 1.2, 'icon_name': 'icecream', 'order': 5},
                    {'name': 'With Cream', 'price_multiplier': 1.1, 'icon_name': 'cake', 'order': 6},
                ],
                'Hot Beverages': [
                    {'name': 'Small', 'price_multiplier': 0.8, 'icon_name': 'local_cafe_outlined', 'order': 1},
                    {'name': 'Regular', 'price_multiplier': 1.0, 'icon_name': 'local_cafe', 'order': 2},
                    {'name': 'Large', 'price_multiplier': 1.3, 'icon_name': 'coffee', 'order': 3},
                    {'name': 'Extra Large', 'price_multiplier': 1.5, 'icon_name': 'local_bar', 'order': 4},
                    {'name': 'Decaf', 'price_multiplier': 1.0, 'icon_name': 'nights_stay', 'order': 5},
                    {'name': 'No Milk', 'price_multiplier': 0.9, 'icon_name': 'no_drinks', 'order': 6},
                    {'name': 'Light Milk', 'price_multiplier': 1.0, 'icon_name': 'opacity', 'order': 7},
                    {'name': 'Extra Milk', 'price_multiplier': 1.1, 'icon_name': 'water_drop', 'order': 8},
                    {'name': 'No Sugar', 'price_multiplier': 1.0, 'icon_name': 'heart_broken', 'order': 9},
                    {'name': 'Light Sugar', 'price_multiplier': 1.0, 'icon_name': 'favorite_border', 'order': 10},
                    {'name': 'Extra Sugar', 'price_multiplier': 1.0, 'icon_name': 'favorite', 'order': 11},
                    {'name': 'Oat Milk', 'price_multiplier': 1.1, 'icon_name': 'eco', 'order': 12},
                    {'name': 'Soy Milk', 'price_multiplier': 1.1, 'icon_name': 'eco', 'order': 13},
                ],
                'Cold Drinks': [
                    {'name': '200ml', 'price_multiplier': 0.7, 'icon_name': 'local_drink_outlined', 'order': 1},
                    {'name': '330ml', 'price_multiplier': 1.0, 'icon_name': 'local_drink', 'order': 2},
                    {'name': '500ml', 'price_multiplier': 1.4, 'icon_name': 'sports_bar', 'order': 3},
                    {'name': '1L', 'price_multiplier': 2.0, 'icon_name': 'liquor', 'order': 4},
                    {'name': 'With Ice', 'price_multiplier': 1.0, 'icon_name': 'ac_unit', 'order': 5},
                    {'name': 'No Ice', 'price_multiplier': 1.0, 'icon_name': 'block', 'order': 6},
                    {'name': 'Extra Cold', 'price_multiplier': 1.0, 'icon_name': 'ac_unit', 'order': 7},
                ],
                'Alcoholic Beverages': [
                    {'name': 'Single', 'price_multiplier': 1.0, 'icon_name': 'local_bar_outlined', 'order': 1},
                    {'name': 'Double', 'price_multiplier': 1.8, 'icon_name': 'local_bar', 'order': 2},
                    {'name': 'On the Rocks', 'price_multiplier': 1.0, 'icon_name': 'ac_unit', 'order': 3},
                    {'name': 'Neat', 'price_multiplier': 1.0, 'icon_name': 'wine_bar', 'order': 4},
                    {'name': 'With Mixer', 'price_multiplier': 1.1, 'icon_name': 'local_drink', 'order': 5},
                    {'name': 'Bottle (330ml)', 'price_multiplier': 1.0, 'icon_name': 'sports_bar', 'order': 6},
                    {'name': 'Pint', 'price_multiplier': 1.4, 'icon_name': 'local_bar', 'order': 7},
                    {'name': 'Half Pint', 'price_multiplier': 0.7, 'icon_name': 'local_bar_outlined', 'order': 8},
                    {'name': 'Glass (125ml)', 'price_multiplier': 0.8, 'icon_name': 'wine_bar', 'order': 9},
                    {'name': 'Large Glass (175ml)', 'price_multiplier': 1.2, 'icon_name': 'wine_bar', 'order': 10},
                ],
                'Street Food & Snacks': [
                    {'name': 'Small', 'price_multiplier': 0.8, 'icon_name': 'fastfood_outlined', 'order': 1},
                    {'name': 'Regular', 'price_multiplier': 1.0, 'icon_name': 'fastfood', 'order': 2},
                    {'name': 'Large', 'price_multiplier': 1.3, 'icon_name': 'lunch_dining', 'order': 3},
                    {'name': 'Combo Meal', 'price_multiplier': 1.5, 'icon_name': 'dining', 'order': 4},
                    {'name': 'Extra Cheese', 'price_multiplier': 1.1, 'icon_name': 'add_circle', 'order': 5},
                    {'name': 'Extra Sauce', 'price_multiplier': 1.05, 'icon_name': 'add', 'order': 6},
                    {'name': 'No Onions', 'price_multiplier': 1.0, 'icon_name': 'remove_circle_outline', 'order': 7},
                    {'name': 'Gluten Free', 'price_multiplier': 1.2, 'icon_name': 'eco', 'order': 8},
                ],
                'Appetizers & Tapas': [
                    {'name': 'Half Portion', 'price_multiplier': 0.6, 'icon_name': 'restaurant_outlined', 'order': 1},
                    {'name': 'Full Portion', 'price_multiplier': 1.0, 'icon_name': 'restaurant', 'order': 2},
                    {'name': 'Sharing Platter', 'price_multiplier': 1.8, 'icon_name': 'dining', 'order': 3},
                    {'name': 'With Bread', 'price_multiplier': 1.1, 'icon_name': 'breakfast_dining', 'order': 4},
                    {'name': 'Extra Spicy', 'price_multiplier': 1.0, 'icon_name': 'whatshot', 'order': 5},
                ],
                'Salads & Bowls': [
                    {'name': 'Starter Size', 'price_multiplier': 0.7, 'icon_name': 'eco', 'order': 1},
                    {'name': 'Main Size', 'price_multiplier': 1.0, 'icon_name': 'restaurant', 'order': 2},
                    {'name': 'Add Chicken', 'price_multiplier': 1.3, 'icon_name': 'add_circle', 'order': 3},
                    {'name': 'Add Salmon', 'price_multiplier': 1.5, 'icon_name': 'add_circle', 'order': 4},
                    {'name': 'Extra Dressing', 'price_multiplier': 1.05, 'icon_name': 'add', 'order': 5},
                    {'name': 'No Dressing', 'price_multiplier': 0.95, 'icon_name': 'remove', 'order': 6},
                    {'name': 'Vegan', 'price_multiplier': 1.0, 'icon_name': 'eco', 'order': 7},
                ],
            }
        }
        
        created_count = 0
        skipped_count = 0

        for language, categories in variant_data.items():
            for category_name, variants in categories.items():
                try:
                    category_template = CategoryTemplate.objects.get(name=category_name, language=language)
                    for variant_data_item in variants:
                        _, created = VariantTemplate.objects.get_or_create(
                            category_template=category_template,
                            name=variant_data_item['name'],
                            language=language,
                            defaults={
                                'price_multiplier': variant_data_item['price_multiplier'],
                                'icon_name': variant_data_item['icon_name'],
                                'display_order': variant_data_item['order'],
                            }
                        )
                        if created:
                            created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"'{category_name}' kategorisi ({language}) için {len(variants)} varyant şablonu işlendi."))
                except CategoryTemplate.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"UYARI: '{category_name}' ({language}) isimli kategori şablonu bulunamadı. Bu kategori atlanıyor."))
                    skipped_count += 1

        self.stdout.write(self.style.SUCCESS(f'İşlem tamamlandı. {created_count} yeni varyant şablonu eklendi. {skipped_count} kategori atlandı.'))