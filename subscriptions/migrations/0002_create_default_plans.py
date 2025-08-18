# subscriptions/migrations/0002_create_default_plans.py

from django.db import migrations

def create_plans(apps, schema_editor):
    Plan = apps.get_model('subscriptions', 'Plan')
    
    Plan.objects.create(
        name="Temel Paket",
        google_product_id_monthly="aylik_abonelik_01",
        google_product_id_yearly="yillik_abonelik_01",
        apple_product_id_monthly="aylik_abonelik_01",
        apple_product_id_yearly="yillik_abonelik_01",
        max_tables=10, max_staff=2, max_kds_screens=2,
        max_categories=4, max_menu_items=20, max_variants=50
    )
    Plan.objects.create(
        name="Silver Paket",
        google_product_id_monthly="silver_aylik_paket_01",
        google_product_id_yearly="silver_yillik_paket_01",
        apple_product_id_monthly="silver_aylik_paket_01",
        apple_product_id_yearly="silver_yillik_paket_01",
        max_tables=50, max_staff=10, max_kds_screens=4,
        max_categories=25, max_menu_items=100, max_variants=100
    )
    Plan.objects.create(
        name="Gold Paket",
        google_product_id_monthly="gold_aylik_paket_01",
        google_product_id_yearly="gold_yillik_paket_01",
        apple_product_id_monthly="gold_aylik_paket_01",
        apple_product_id_yearly="gold_yillik_paket_01",
        max_tables=120, max_staff=50, max_kds_screens=10,
        max_categories=100, max_menu_items=500, max_variants=1000
    )

def remove_plans(apps, schema_editor):
    Plan = apps.get_model('subscriptions', 'Plan')
    Plan.objects.filter(name__in=["Temel Paket", "Silver Paket", "Gold Paket"]).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('subscriptions', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(create_plans, remove_plans),
    ]