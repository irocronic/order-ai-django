# subscriptions/models.py

from django.db import models
from django.conf import settings
from core.models import Business

class Plan(models.Model):
    """
    Farklı abonelik katmanlarını (Temel, Silver, Gold vb.) ve limitlerini tanımlar.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Plan Adı")
    
    # Google Play Store ve Apple App Store için ürün ID'leri
    google_product_id_monthly = models.CharField(max_length=255, unique=True, null=True, blank=True, verbose_name="Google Play Aylık ID")
    google_product_id_yearly = models.CharField(max_length=255, unique=True, null=True, blank=True, verbose_name="Google Play Yıllık ID")
    apple_product_id_monthly = models.CharField(max_length=255, unique=True, null=True, blank=True, verbose_name="App Store Aylık ID")
    apple_product_id_yearly = models.CharField(max_length=255, unique=True, null=True, blank=True, verbose_name="App Store Yıllık ID")
    
    # Planda tanımlı limitler
    max_tables = models.PositiveIntegerField(default=10, verbose_name="Maks. Masa Sayısı")
    max_staff = models.PositiveIntegerField(default=2, verbose_name="Maks. Personel Sayısı")
    max_kds_screens = models.PositiveIntegerField(default=2, verbose_name="Maks. KDS Ekranı")
    max_categories = models.PositiveIntegerField(default=4, verbose_name="Maks. Kategori Sayısı")
    max_menu_items = models.PositiveIntegerField(default=20, verbose_name="Maks. Menü Ürünü")
    max_variants = models.PositiveIntegerField(default=50, verbose_name="Maks. Ürün Varyantı")
    
    is_active = models.BooleanField(default=True, verbose_name="Seçilebilir mi?")

    class Meta:
        verbose_name = "Abonelik Planı"
        verbose_name_plural = "Abonelik Planları"
        ordering = ['max_tables']

    def __str__(self):
        return self.name

class Subscription(models.Model):
    """
    Bir işletmenin mevcut abonelik durumunu ve hangi plana sahip olduğunu tutar.
    """
    STATUS_CHOICES = [
        ('active', 'Aktif'),
        ('trial', 'Deneme Süresinde'),
        ('inactive', 'Pasif (Süre Doldu/Ödenmedi)'),
        ('cancelled', 'İptal Edildi'),
    ]
    
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriptions', verbose_name="Abonelik Planı")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial', verbose_name="Durum")
    provider = models.CharField(max_length=50, blank=True, null=True, verbose_name="Sağlayıcı (Google/Apple)")
    provider_subscription_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Sağlayıcı Abonelik ID")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Bitiş Tarihi")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business.name} - {self.plan.name if self.plan else 'Plansız'} ({self.get_status_display()})"

    class Meta:
        verbose_name = "İşletme Aboneliği"
        verbose_name_plural = "İşletme Abonelikleri"