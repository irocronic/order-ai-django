# Düzeltilmiş 0002_initial_plans.py

from django.db import migrations

def create_initial_plans(apps, schema_editor):
    Plan = apps.get_model('subscriptions', 'Plan')
    
    # Temel Plan
    Plan.objects.get_or_create(
        name='Temel Plan',
        defaults={
            'google_product_id_monthly': 'temel_aylik_01',   # <-- DEĞİŞTİ
            'google_product_id_yearly': 'temel_yillik_01',    # <-- DEĞİŞTİ
            'apple_product_id_monthly': 'temel_aylik_ios_01', # <-- DEĞİŞTİ
            'apple_product_id_yearly': 'temel_yillik_ios_01', # <-- DEĞİŞTİ
            'max_tables': 10,
            'max_staff': 3,
            'max_kds_screens': 1,
            'max_categories': 10,
            'max_menu_items': 50,
            'max_variants': 100,
            'is_active': True,
        }
    )
    
    # Silver Plan
    Plan.objects.get_or_create(
        name='Silver Plan',
        defaults={
            'google_product_id_monthly': 'silver_aylik_01',  # <-- DEĞİŞTİ
            'google_product_id_yearly': 'silver_yillik_01',   # <-- DEĞİŞTİ
            'apple_product_id_monthly': 'silver_aylik_ios_01',# <-- DEĞİŞTİ
            'apple_product_id_yearly': 'silver_yillik_ios_01',# <-- DEĞİŞTİ
            'max_tables': 50,
            'max_staff': 10,
            'max_kds_screens': 4,
            'max_categories': 25,
            'max_menu_items': 100,
            'max_variants': 250,
            'is_active': True,
        }
    )
    # Diğer planlar için de ID'leri benzersiz yap...

class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_plans),
    ]