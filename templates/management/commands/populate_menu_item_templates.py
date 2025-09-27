# templates/management/commands/populate_menu_item_templates.py

from django.core.management.base import BaseCommand
from templates.models import CategoryTemplate, MenuItemTemplate

class Command(BaseCommand):
    help = 'Hazır menü öğesi şablonlarını ilgili kategori şablonlarına göre veritabanına ekler.'

    def handle(self, *args, **options):
        menu_data = {
            # TÜRKÇE MENÜLER
            'tr': {
                'Ana Yemekler': ['Spaghetti Bolonez', 'Fettuccine Alfredo', 'Penne Arabiata', 'Ravioli', 'Tagliatelle', 'Lazanya', 'Pilav', 'Bulgur Pilavı', 'İç Pilav', 'Kuru Fasulye', 'Nohut', 'İskender', 'Adana Kebap', 'Urfa Kebap', 'Beyti Kebap', 'Alinazik', 'Hünkar Beğendi', 'Ali Nazik Kebabı', 'Tavuk Şiş', 'Et Şiş', 'Et Döner', 'Tavuk Döner', 'Ciğer Şiş', 'Lahmacun', 'Pide', 'Karışık Izgara', 'Köfte Izgara', 'Kaşarlı Köfte', 'Akçaabat Köftesi', 'Kasap Köfte', 'Tavuk Kanat', 'Tavuk Pirzola', 'Tavuk Göğüs Izgara', 'Balık Izgara', 'Hamsi Tava', 'Palamut Izgara', 'Karışık Güveç', 'Etli Kuru Bamya', 'Et Sote', 'Tavuk Sote', 'Sac Kavurma', 'Çoban Kavurma', 'Musakka', 'Karnıyarık', 'Kabak Dolması', 'Biber Dolması', 'Patlıcan Musakka', 'Kuşbaşılı Kaşarlı Güveç'],
                'Çorbalar': ['Mercimek Çorbası', 'Ezogelin Çorbası', 'Yayla Çorbası', 'Tarhana Çorbası', 'Domates Çorbası', 'İşkembe Çorbası', 'Tavuk Suyu Çorbası', 'Balık Çorbası'],
                'Mezeler & Aperatifler': ['Haydari', 'Atom', 'Acılı Ezme', 'Şakşuka', 'Fava', 'Patlıcan Ezmesi', 'Muhammara', 'Kısır', 'Zeytinyağlı Yaprak Sarma', 'Rus Salatası', 'Patates Salatası', 'Havuç Tarator', 'Barbunya Pilaki', 'Enginar Dolması', 'Mücver', 'Girit Ezmesi', 'Kabak Tarator', 'Humus', 'Babagannuş'],
                'Salatalar': ['Gavurdağı Salatası', 'Piyaz', 'Çoban Salata', 'Mevsim Salata', 'Akdeniz Salata', 'Ton Balıklı Salata', 'Tavuklu Sezar Salata', 'Noodle Salata'],
                'Atıştırmalıklar & Fast Food': ['Hamburger', 'Cheeseburger', 'Double Burger', 'Tavuk Burger', 'Fish Burger', 'Vejetaryen Burger', 'Patates Kızartması', 'Soğan Halkası', 'Pizza', 'Calzone', 'Tost', 'Simit', 'Açma', 'Poğaça', 'Börek', 'Gözleme', 'Midye Dolma', 'Kokoreç', 'Tantuni', 'Dürüm', 'Çiğköfte Dürüm', 'Balık Ekmek', 'Patso'],
                'Tatlılar': ['Baklava', 'Fıstıklı Baklava', 'Cevizli Baklava', 'Şöbiyet', 'Künefe', 'Katmer', 'Sütlaç', 'Kazandibi', 'Profiterol', 'Revani', 'Tulumba Tatlısı', 'Trileçe', 'Dondurma', 'Cheesecake', 'Magnolia', 'Brownie', 'Mozaik Pasta', 'Lokma', 'Helva', 'Ayva Tatlısı', 'Kabak Tatlısı', 'Keşkül', 'Güllaç', 'Tiramisu', 'Ekler', 'Parfe', 'Supangle', 'Panna Cotta'],
                'Soğuk İçecekler': ['Coca Cola', 'Pepsi', 'Fanta', 'Sprite', 'Ice Tea', 'Ayran', 'Şalgam', 'Soda', 'Meyve Suyu', 'Limonata', 'Soğuk Kahve', 'Smoothie', 'Milkshake', 'Mojito', 'Virgin Pina Colada', 'Bubble Tea'],
                'Sıcak İçecekler': ['Çay', 'Türk Kahvesi', 'Filtre Kahve', 'Latte', 'Cappuccino', 'Espresso', 'Americano', 'Mocha', 'Macchiato', 'Flat White', 'Cortado', 'Ristretto', 'Affogato', 'Salep', 'Bitki Çayı', 'Kış Çayı', 'Kakao'],
                'Alkollü İçecekler': [
                    # Bira
                    'Efes', 'Tuborg', 'Heineken', 'Corona', 'Stella Artois', 'Bomonti', 'Carlsberg', 'Guinness',
                    # Rakı
                    'Yeni Rakı', 'Tekirdağ Rakısı', 'Kulüp Rakısı', 'Altınbaş Rakısı', 'İzmir Rakısı',
                    # Şarap
                    'Kırmızı Şarap', 'Beyaz Şarap', 'Rosé Şarap', 'Champagne', 'Prosecco', 'Kavaklidere', 'Doluca', 'Kayra',
                    # Viski
                    'Johnnie Walker', 'Jack Daniels', 'Chivas Regal', 'Ballantines', 'Jameson', 'Tekel Gold',
                    # Votka
                    'Absolut', 'Smirnoff', 'Grey Goose', 'Beluga', 'Russian Standard',
                    # Cin
                    'Bombay Sapphire', 'Hendricks', 'Tanqueray', 'Beefeater',
                    # Rom
                    'Bacardi', 'Captain Morgan', 'Havana Club', 'Mount Gay',
                    # Likör
                    'Baileys', 'Kahlua', 'Amaretto', 'Frangelico', 'Cointreau', 'Grand Marnier',
                    # Kokteyller
                    'Mojito', 'Caipirinha', 'Margarita', 'Cosmopolitan', 'Long Island', 'Pina Colada', 'Bloody Mary', 'Moscow Mule', 'Whiskey Sour', 'Old Fashioned', 'Negroni', 'Aperol Spritz', 'Gin Tonic', 'Screwdriver', 'Sex on the Beach'
                ]
            },
            
            # İNGİLİZCE MENÜLER (AVRUPA POPÜLERİ)
            'en': {
                'Main Courses': [
                    # İtalyan
                    'Spaghetti Carbonara', 'Margherita Pizza', 'Quattro Stagioni Pizza', 'Risotto Milanese', 'Osso Buco', 'Lasagna Bolognese', 'Penne Arrabbiata', 'Fettuccine Alfredo', 'Gnocchi Sorrentina', 'Ravioli Spinaci',
                    # Fransız
                    'Beef Bourguignon', 'Coq au Vin', 'Ratatouille', 'Croque Monsieur', 'Bouillabaisse', 'Duck Confit', 'Cassoulet', 'Quiche Lorraine',
                    # İngiliz
                    'Fish & Chips', 'Bangers & Mash', 'Shepherd\'s Pie', 'Beef Wellington', 'Sunday Roast', 'Steak & Kidney Pie',
                    # Alman
                    'Schnitzel Vienna', 'Sauerbraten', 'Bratwurst', 'Spätzle', 'Schweinshaxe',
                    # İspanyol
                    'Paella Valenciana', 'Jamón Ibérico', 'Tortilla Española', 'Gazpacho',
                    # Genel Avrupa
                    'Grilled Salmon', 'Chicken Parmesan', 'Beef Stroganoff', 'Lamb Chops', 'Pork Tenderloin', 'Sea Bass', 'Ribeye Steak', 'Chicken Marsala'
                ],
                'Soups & Starters': [
                    'French Onion Soup', 'Minestrone', 'Tomato Basil Soup', 'Mushroom Soup', 'Clam Chowder', 'Gazpacho', 'Butternut Squash Soup', 'Chicken Noodle Soup', 'Leek & Potato Soup', 'Seafood Bisque'
                ],
                'Appetizers & Tapas': [
                    # İspanyol Tapas
                    'Patatas Bravas', 'Jamón Serrano', 'Manchego Cheese', 'Albondigas', 'Gambas al Ajillo', 'Pimientos de Padrón', 'Croquetas',
                    # İtalyan Antipasti
                    'Bruschetta', 'Antipasto Platter', 'Caprese Salad', 'Prosciutto e Melone', 'Arancini', 'Calamari Fritti',
                    # Fransız
                    'Escargot', 'Pâté de Foie Gras', 'Cheese Board', 'Oysters Rockefeller',
                    # Genel
                    'Hummus & Pita', 'Stuffed Mushrooms', 'Garlic Bread', 'Olives & Nuts', 'Charcuterie Board'
                ],
                'Salads & Bowls': [
                    'Caesar Salad', 'Greek Salad', 'Niçoise Salad', 'Waldorf Salad', 'Caprese Salad', 'Arugula Salad', 'Quinoa Bowl', 'Buddha Bowl', 'Mediterranean Bowl', 'Tuna Salad', 'Chicken Caesar', 'Pasta Salad'
                ],
                'Street Food & Snacks': [
                    # Amerikan Fast Food
                    'Classic Burger', 'Cheeseburger', 'BBQ Bacon Burger', 'Chicken Burger', 'Fish Burger', 'Veggie Burger', 'French Fries', 'Onion Rings', 'Chicken Wings', 'Nachos',
                    # Avrupa Street Food
                    'Döner Kebab', 'Currywurst', 'Bratwurst', 'Crêpes', 'Panini', 'Focaccia', 'Baguette Sandwich', 'Fish & Chips', 'Hot Dog', 'Pretzel',
                    # Pizza & İtalyan
                    'Margherita Pizza', 'Pepperoni Pizza', 'Quattro Formaggi', 'Calzone', 'Garlic Bread'
                ],
                'Desserts & Sweets': [
                    # Fransız
                    'Crème Brûlée', 'Macarons', 'Éclair', 'Profiteroles', 'Tarte Tatin', 'Mille-feuille', 'Madeleines',
                    # İtalyan
                    'Tiramisu', 'Panna Cotta', 'Gelato', 'Cannoli', 'Affogato', 'Zabaglione',
                    # İngiliz
                    'Sticky Toffee Pudding', 'Eton Mess', 'Scones', 'Victoria Sponge', 'Banoffee Pie',
                    # Alman/Avusturya
                    'Black Forest Cake', 'Apple Strudel', 'Sachertorte',
                    # Genel
                    'Cheesecake', 'Chocolate Mousse', 'Lemon Tart', 'Ice Cream', 'Sorbet', 'Brownie', 'Cookies', 'Fruit Tart'
                ],
                'Hot Beverages': [
                    # Kahve
                    'Espresso', 'Americano', 'Cappuccino', 'Latte', 'Macchiato', 'Mocha', 'Flat White', 'Cortado', 'Ristretto', 'Affogato', 'Irish Coffee', 'Vienna Coffee',
                    # Çay
                    'English Breakfast Tea', 'Earl Grey', 'Green Tea', 'Chamomile Tea', 'Mint Tea', 'Herbal Tea', 'Chai Latte',
                    # Diğer
                    'Hot Chocolate', 'Mulled Wine', 'Hot Toddy'
                ],
                'Cold Drinks': [
                    # Gazlı İçecekler
                    'Coca Cola', 'Pepsi', 'Sprite', 'Fanta', 'Tonic Water', 'Ginger Ale', 'Lemonade', 'Iced Tea',
                    # Meyve Suları
                    'Orange Juice', 'Apple Juice', 'Cranberry Juice', 'Pineapple Juice', 'Tomato Juice',
                    # Özel İçecekler
                    'Smoothie', 'Milkshake', 'Iced Coffee', 'Frappé', 'Virgin Mojito', 'Arnold Palmer', 'Sparkling Water', 'Still Water'
                ],
                'Alcoholic Beverages': [
                    # Bira
                    'Heineken', 'Stella Artois', 'Corona', 'Guinness', 'Carlsberg', 'Peroni', 'Beck\'s', 'Budweiser', 'Pilsner Urquell', 'Leffe',
                    # Şarap
                    'Bordeaux Red', 'Burgundy White', 'Chianti', 'Prosecco', 'Champagne', 'Rosé Wine', 'Pinot Grigio', 'Cabernet Sauvignon', 'Sauvignon Blanc', 'Merlot',
                    # Viski
                    'Johnnie Walker', 'Jack Daniel\'s', 'Jameson', 'Macallan', 'Glenfiddich', 'Chivas Regal', 'Ballantine\'s',
                    # Vodka
                    'Absolut', 'Grey Goose', 'Beluga', 'Smirnoff', 'Stolichnaya',
                    # Cin
                    'Bombay Sapphire', 'Hendrick\'s', 'Tanqueray', 'Beefeater', 'Gin Mare',
                    # Rom
                    'Bacardi', 'Captain Morgan', 'Havana Club', 'Mount Gay',
                    # Likör
                    'Baileys', 'Kahlúa', 'Amaretto', 'Cointreau', 'Grand Marnier', 'Limoncello',
                    # Kokteyller
                    'Mojito', 'Margarita', 'Cosmopolitan', 'Piña Colada', 'Long Island Iced Tea', 'Bloody Mary', 'Moscow Mule', 'Whiskey Sour', 'Old Fashioned', 'Negroni', 'Aperol Spritz', 'Gin & Tonic', 'Manhattan', 'Daiquiri', 'Caipirinha'
                ]
            }
        }
        
        created_count = 0
        skipped_count = 0

        for language, categories in menu_data.items():
            for category_name, items in categories.items():
                try:
                    category_template = CategoryTemplate.objects.get(name=category_name, language=language)
                    for item_name in items:
                        _, created = MenuItemTemplate.objects.get_or_create(
                            category_template=category_template,
                            name=item_name,
                            language=language
                        )
                        if created:
                            created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"'{category_name}' kategorisi ({language}) için {len(items)} ürün şablonu işlendi."))
                except CategoryTemplate.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"UYARI: '{category_name}' ({language}) isimli kategori şablonu bulunamadı. Bu kategori atlanıyor."))
                    skipped_count += 1

        self.stdout.write(self.style.SUCCESS(f'İşlem tamamlandı. {created_count} yeni ürün şablonu eklendi. {skipped_count} kategori atlandı.'))