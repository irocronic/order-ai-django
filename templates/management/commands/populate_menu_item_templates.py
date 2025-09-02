# templates/management/commands/populate_menu_item_templates.py

from django.core.management.base import BaseCommand
from templates.models import CategoryTemplate, MenuItemTemplate

class Command(BaseCommand):
    help = 'Hazır menü öğesi şablonlarını ilgili kategori şablonlarına göre veritabanına ekler.'

    def handle(self, *args, **options):
        # Sağladığınız ürün listesi
        menu_data = {
            'Ana Yemekler': ['Spaghetti Bolonez', 'Fettuccine Alfredo', 'Penne Arabiata', 'Ravioli', 'Tagliatelle', 'Lazanya', 'Pilav', 'Bulgur Pilavı', 'İç Pilav', 'Kuru Fasulye', 'Nohut', 'Mercimek Çorbası', 'Ezogelin Çorbası', 'Yayla Çorbası', 'Tarhana Çorbası', 'Domates Çorbası', 'İşkembe Çorbası', 'Tavuk Suyu Çorbası', 'Balık Çorbası', 'İskender', 'Adana Kebap', 'Urfa Kebap', 'Beyti Kebap', 'Alinazik', 'Hünkar Beğendi', 'Ali Nazik Kebabı', 'Tavuk Şiş', 'Et Şiş', 'Et Döner', 'Tavuk Döner', 'Ciğer Şiş', 'Lahmacun', 'Pide', 'Karışık Izgara', 'Köfte Izgara', 'Kaşarlı Köfte', 'Akçaabat Köftesi', 'Kasap Köfte', 'Tavuk Kanat', 'Tavuk Pirzola', 'Tavuk Göğüs Izgara', 'Balık Izgara', 'Hamsi Tava', 'Palamut Izgara', 'Karışık Güveç', 'Etli Kuru Bamya', 'Et Sote', 'Tavuk Sote', 'Sac Kavurma', 'Çoban Kavurma', 'Musakka', 'Karnıyarık', 'Kabak Dolması', 'Biber Dolması', 'Patlıcan Musakka', 'Kuşbaşılı Kaşarlı Güveç'],
            'Mezeler & Aperatifler': ['Haydari', 'Atom', 'Acılı Ezme', 'Şakşuka', 'Fava', 'Patlıcan Ezmesi', 'Muhammara', 'Kısır', 'Zeytinyağlı Yaprak Sarma', 'Rus Salatası', 'Patates Salatası', 'Havuç Tarator', 'Barbunya Pilaki', 'Enginar Dolması', 'Mücver', 'Girit Ezmesi', 'Kabak Tarator', 'Humus', 'Babagannuş', 'Gavurdağı Salatası', 'Piyaz', 'Çoban Salata', 'Mevsim Salata', 'Akdeniz Salata', 'Ton Balıklı Salata', 'Tavuklu Sezar Salata', 'Noodle Salata'],
            'Atıştırmalıklar & Fast Food': ['Hamburger', 'Cheeseburger', 'Double Burger', 'Tavuk Burger', 'Fish Burger', 'Vejetaryen Burger', 'Patates Kızartması', 'Soğan Halkası', 'Pizza', 'Calzone', 'Tost', 'Simit', 'Açma', 'Poğaça', 'Börek', 'Gözleme', 'Midye Dolma', 'Kokoreç', 'Tantuni', 'Dürüm', 'Çiğköfte Dürüm', 'Balık Ekmek', 'Patso'],
            'Tatlılar': ['Baklava', 'Fıstıklı Baklava', 'Cevizli Baklava', 'Şöbiyet', 'Künefe', 'Katmer', 'Sütlaç', 'Kazandibi', 'Profiterol', 'Revani', 'Tulumba Tatlısı', 'Trileçe', 'Dondurma', 'Cheesecake', 'Magnolia', 'Brownie', 'Mozaik Pasta', 'Lokma', 'Helva', 'Ayva Tatlısı', 'Kabak Tatlısı', 'Keşkül', 'Güllaç', 'Tiramisu', 'Ekler', 'Parfe', 'Supangle', 'Panna Cotta'],
            'Soğuk İçecekler': ['Coca Cola', 'Pepsi', 'Fanta', 'Sprite', 'Ice Tea', 'Ayran', 'Şalgam', 'Soda', 'Meyve Suyu', 'Limonata', 'Soğuk Kahve', 'Smoothie', 'Milkshake', 'Mojito', 'Virgin Pina Colada', 'Bubble Tea'],
            'Sıcak İçecekler': ['Çay', 'Türk Kahvesi', 'Filtre Kahve', 'Latte', 'Cappuccino', 'Espresso', 'Americano', 'Mocha', 'Macchiato', 'Flat White', 'Cortado', 'Ristretto', 'Affogato', 'Salep', 'Bitki Çayı', 'Kış Çayı', 'Kakao']
        }

        created_count = 0
        skipped_count = 0

        for category_name, items in menu_data.items():
            try:
                # Önce Türkçe kategori şablonunu bul
                category_template = CategoryTemplate.objects.get(name=category_name, language='tr')
                for item_name in items:
                    _, created = MenuItemTemplate.objects.get_or_create(
                        category_template=category_template,
                        name=item_name,
                        language='tr'
                    )
                    if created:
                        created_count += 1
                self.stdout.write(self.style.SUCCESS(f"'{category_name}' kategorisi için {len(items)} ürün şablonu işlendi."))
            except CategoryTemplate.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"UYARI: '{category_name}' isimli kategori şablonu bulunamadı. Bu kategori atlanıyor."))
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(f'İşlem tamamlandı. {created_count} yeni ürün şablonu eklendi. {skipped_count} kategori atlandı.'))