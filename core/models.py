# core/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.conf import settings
import uuid
from django.utils import timezone
from datetime import timedelta
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from encrypted_model_fields.fields import EncryptedCharField
import pytz

# === YENİ KOD BAŞLANGICI: CustomUserManager ===
# Bu sınıf, 'createsuperuser' komutunun davranışını özelleştirir.
class CustomUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # Superuser için is_staff ve is_superuser alanlarını True yapar.
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # EN ÖNEMLİ DÜZELTME: user_type alanını 'admin' olarak ayarlar.
        extra_fields.setdefault("user_type", "admin")
        # Adminin ayrıca bir onaya ihtiyacı yoktur.
        extra_fields.setdefault("is_approved_by_admin", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(username, email, password, **extra_fields)
# === YENİ KOD SONU ===

STAFF_PERMISSION_CHOICES = [
    ('view_reports', 'Raporları Görüntüleme'),
    ('manage_credit_sales', 'Veresiye Satış Yönetimi'),
    ('manage_menu', 'Menü Yönetimi (Kategori, Ürün, Varyant)'),
    ('manage_stock', 'Stok Yönetimi'),
    ('manage_tables', 'Masa Yönetimi'),
    ('view_completed_orders', 'Tamamlanmış Siparişleri Görüntüleme'),
    ('view_pending_orders', 'Bekleyen Siparişleri Görüntüleme'),
    ('take_orders', 'Sipariş Alma (Masa/Paket)'),
    ('manage_staff', 'Personel Yönetimi'),
    ('manage_waiting_customers', 'Bekleyen Müşteri Yönetimi'),
    ('view_account_settings', 'Hesap Ayarlarını Görüntüleme/Düzenleme'),
    ('manage_kds', 'Mutfak Ekranını Kullanma/Yönetme (Genel)'),
    ('manage_kds_screens', 'KDS Ekran Tanımlarını Yönetme (Ekle/Sil/Düzenle)'),
    ('manage_pagers', 'Çağrı Cihazı Yönetimi'),
    ('manage_campaigns', 'Kampanya Yönetimi'),
    ('manage_attendance', 'Personel Giriş-Çıkış Yönetimi'),  # YENİ EKLENEN
]

NOTIFICATION_EVENT_TYPES = [
    ('guest_order_pending_approval', 'Misafir Siparişi Onay Bekliyor'),
    ('order_pending_approval', 'Kayıtlı Kullanıcı Siparişi Onay Bekliyor'),
    ('existing_order_needs_reapproval', 'Mevcut Sipariş Tekrar Onay Bekliyor'),
    ('new_approved_order', 'Yeni Onaylanmış Sipariş (Personel/İşletme Sahibi)'),
    ('order_approved_for_kitchen', 'Sipariş Onaylandı (Mutfağa İletildi)'),
    ('order_preparing_update', 'Sipariş Mutfakta Hazırlanıyor'),
    ('order_ready_for_pickup_update', 'Sipariş Mutfakta Hazır (Alınmayı Bekliyor)'),
    ('order_picked_up_by_waiter', 'Sipariş Garson Tarafından Mutfaktan Alındı'),
    ('order_out_for_delivery_update', 'Sipariş Teslime Hazır (Müşteriye Gidiyor)'),
    ('order_item_delivered', 'Sipariş Kalemi Teslim Edildi'),
    ('order_fully_delivered', 'Sipariş Tümüyle Teslim Edildi'),
    ('order_completed_update', 'Sipariş Tamamlandı (Ödendi)'),
    ('order_cancelled_update', 'Sipariş İptal Edildi'),
    ('order_rejected_update', 'Sipariş Reddedildi'),
    ('order_updated', 'Sipariş Genel Güncellemesi'),
    ('order_item_added', 'Siparişe Ürün Eklendi'),
    ('order_item_removed', 'Siparişten Ürün Çıkarıldı'),
    ('order_item_updated', 'Sipariş Kalemi Güncellendi'),
    ('order_transferred', 'Sipariş Başka Masaya Transfer Edildi'),
    ('waiting_customer_added', 'Yeni Bekleyen Müşteri Eklendi'),
    ('waiting_customer_updated', 'Bekleyen Müşteri Güncellendi'),
    ('waiting_customer_removed', 'Bekleyen Müşteri Silindi'),
    ('waiting_customer_seated', 'Bekleyen Müşteri Oturtuldu'),
    ('stock_adjusted', 'Stok Ayarlandı/Güncellendi'),
    ('pager_status_updated', 'Çağrı Cihazı Durumu Güncellendi'),
    ('reservation_pending_approval', 'Yeni Rezervasyon Onay Bekliyor'),
    ('staff_check_in', 'Personel Giriş Yaptı'),  # YENİ EKLENEN
    ('staff_check_out', 'Personel Çıkış Yaptı'),  # YENİ EKLENEN
]

DEFAULT_BUSINESS_OWNER_NOTIFICATION_PERMISSIONS = [key for key, desc in NOTIFICATION_EVENT_TYPES]
DEFAULT_STAFF_NOTIFICATION_PERMISSIONS = [
    'order_ready_for_pickup_update',
    'order_picked_up_by_waiter',
    'order_out_for_delivery_update',
    'order_item_delivered',
    'waiting_customer_seated',
    'pager_status_updated',
]
DEFAULT_KITCHEN_NOTIFICATION_PERMISSIONS = [
    'order_approved_for_kitchen',
    'order_item_added',
    'order_updated',
]

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('business_owner', 'İşletme Sahibi'),
        ('customer', 'Müşteri'),
        ('staff', 'Personel'),
        ('kitchen_staff', 'Mutfak Personeli'),
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='customer')
    profile_image_url = models.URLField(
        max_length=1024,
        blank=True,
        null=True,
        verbose_name="Profil Fotoğrafı URL'i"
    )
    associated_business = models.ForeignKey(
        'Business',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='staff_members',
        help_text="Kullanıcı 'Personel' veya 'Mutfak Personeli' tipindeyse hangi işletmeye bağlı olduğunu gösterir."
    )
    staff_permissions = models.JSONField(
        default=list,
        blank=True,
        help_text="Personelin veya Mutfak Personelinin erişebileceği ekran/özellik anahtarlarının listesi (JSON formatında)."
    )
    notification_permissions = models.JSONField(
        default=list,
        blank=True,
        help_text="Kullanıcının abone olduğu bildirim olay türlerinin listesi (JSON formatında). Örn: ['order_approved_for_kitchen', 'waiting_customer_added']"
    )
    is_approved_by_admin = models.BooleanField(
        default=False,
        help_text="Yöneticinin bu kullanıcı hesabını onaylayıp onaylamadığını belirtir."
    )
    accessible_kds_screens = models.ManyToManyField(
        'KDSScreen',
        blank=True,
        related_name='authorized_staff',
        verbose_name="Erişilebilir KDS Ekranları",
        help_text="Personelin veya Mutfak Personelinin erişebileceği KDS ekranları."
    )
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_set_%(app_label)s_%(class)s',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_set_%(app_label)s_%(class)s',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )

    # === YENİ SATIR: Django'ya artık bizim özel user manager'ımızı kullanmasını söylüyoruz ===
    objects = CustomUserManager()

    def __str__(self):
        return self.username

class Business(models.Model):
    owner = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='owned_business',
        limit_choices_to={'user_type': 'business_owner'},
        help_text="Bu işletmenin sahibi olan kullanıcı."
    )
    name = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon Numarası")
    is_setup_complete = models.BooleanField(default=False, help_text="İşletme sahibi kurulum sihirbazını tamamladı mı?")

    class Currency(models.TextChoices):
        TRY = 'TRY', _('Türk Lirası (₺)')
        USD = 'USD', _('ABD Doları ($)')
        EUR = 'EUR', _('Euro (€)')
        GBP = 'GBP', _('İngiliz Sterlini (£)')

    currency_code = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.TRY,
        verbose_name=_("Para Birimi")
    )

    TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.common_timezones]

    timezone = models.CharField(
        max_length=100,
        choices=TIMEZONE_CHOICES,
        default='Europe/Istanbul',
        verbose_name="Zaman Dilimi",
        help_text="İşletmenin bulunduğu yerel zaman dilimi."
    )
    
    # === YENİ ALAN BAŞLANGICI ===
    slug = models.SlugField(
        max_length=100, 
        unique=True, 
        blank=True, 
        verbose_name="URL Slug"
    )
    # === YENİ ALAN SONU ===

    def __str__(self):
        return self.name
    
    # === YENİ METOT BAŞLANGICI ===
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            # Eğer aynı slug varsa unique hale getir
            counter = 1
            original_slug = self.slug
            while Business.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        super().save(*args, **kwargs)
        
        # Website objesi otomatik oluştur
        if not hasattr(self, 'website'):
            BusinessWebsite.objects.create(business=self)
    # === YENİ METOT SONU ===


    class PaymentProvider(models.TextChoices):
        NONE = 'none', 'Entegrasyon Yok'
        IYZICO = 'iyzico', 'Iyzico'
        PAYTR = 'paytr', 'PayTR'
        # Gelecekte eklenecek diğer sağlayıcılar buraya gelebilir.

    payment_provider = models.CharField(
        max_length=20,
        choices=PaymentProvider.choices,
        default=PaymentProvider.NONE,
        verbose_name="Ödeme Sağlayıcı"
    )

    payment_api_key = EncryptedCharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Ödeme Sağlayıcı API Anahtarı"
    )

    payment_secret_key = EncryptedCharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Ödeme Sağlayıcı Gizli Anahtarı"
    )

# === YENİ MODELLER: Tedarikçi ve Alım Yönetimi ===

class Supplier(models.Model):
    """
    Malzeme alımı yapılan tedarikçileri temsil eder.
    """
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='suppliers', verbose_name="İşletme")
    name = models.CharField(max_length=200, verbose_name="Tedarikçi Adı")
    contact_person = models.CharField(max_length=150, blank=True, null=True, verbose_name="Yetkili Kişi")
    email = models.EmailField(max_length=255, blank=True, null=True, verbose_name="E-posta Adresi", help_text="Düşük stok bildirimleri bu adrese gönderilir.")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon")
    address = models.TextField(blank=True, null=True, verbose_name="Adres")

    class Meta:
        verbose_name = "Tedarikçi"
        verbose_name_plural = "Tedarikçiler"
        unique_together = ('business', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name

class PurchaseOrder(models.Model):
    """
    Tedarikçilerden yapılan alımları (faturaları) temsil eder.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', _('Beklemede')
        COMPLETED = 'completed', _('Tamamlandı')
        CANCELLED = 'cancelled', _('İptal Edildi')

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='purchase_orders', verbose_name="İşletme")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders', verbose_name="Tedarikçi")
    order_date = models.DateTimeField(default=timezone.now, verbose_name="Alım Tarihi")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="Durum")
    notes = models.TextField(blank=True, null=True, verbose_name="Notlar")
    invoice_image_url = models.URLField(max_length=1024, blank=True, null=True, verbose_name="Fatura Görseli URL")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Toplam Tutar")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Alım Faturası"
        verbose_name_plural = "Alım Faturaları"
        ordering = ['-order_date']

    def __str__(self):
        return f"Alım #{self.id} - {self.supplier.name} ({self.order_date.strftime('%d.%m.%Y')})"

class UnitOfMeasure(models.Model):
    """Ölçü birimlerini tanımlar (örn: Gram, Adet, Litre)."""
    name = models.CharField(max_length=50, unique=True, verbose_name="Birim Adı") # örn: Gram
    abbreviation = models.CharField(max_length=10, unique=True, verbose_name="Kısaltma") # örn: gr

    class Meta:
        verbose_name = "Ölçü Birimi"
        verbose_name_plural = "Ölçü Birimleri"

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

class Ingredient(models.Model):
    """
    Stok takibi yapılacak her bir envanter kalemini temsil eder.
    Bu bir hammadde (un, kıyma) veya doğrudan satılan bir ürün (Kutu Kola) olabilir.
    """
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='ingredients', verbose_name="İşletme")
    name = models.CharField(max_length=150, verbose_name="Envanter Kalemi Adı")
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, verbose_name="Ölçü Birimi")
    stock_quantity = models.DecimalField(max_digits=10, decimal_places=3, default=0.000, verbose_name="Stok Miktarı")
    
    # --- ESKI Stock modelinden taşınan alan ---
    track_stock = models.BooleanField(
        default=True,
        verbose_name="Stok Takibi Aktif",
        help_text="Bu ürünün stoğu takip edilecek mi? Pasif ise miktar ve uyarılar dikkate alınmaz."
    )
    # ----------------------------------------------
    
    alert_threshold = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Uyarı Eşiği")
    last_updated = models.DateTimeField(auto_now=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='ingredients', verbose_name="Tedarikçi")
    cost_price = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Birim Maliyet Fiyatı")
    low_stock_notification_sent = models.BooleanField(default=False, verbose_name="Düşük Stok Bildirimi Gönderildi")
    
    class Meta:
        verbose_name = "Envanter Kalemi"
        verbose_name_plural = "Envanter Kalemleri"
        unique_together = ('business', 'name')
        ordering = ['name']

    def __str__(self):
        track_status = "" if self.track_stock else " (Takip Dışı)"
        return f"{self.name} ({self.stock_quantity} {self.unit.abbreviation}){track_status}"

class PurchaseOrderItem(models.Model):
    """
    Bir alım faturasındaki her bir malzeme kalemini temsil eder.
    """
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items', verbose_name="Alım Faturası")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name='purchase_items', verbose_name="Malzeme")
    quantity = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Miktar")
    unit_price = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Birim Alış Fiyatı (Maliyet)")

    class Meta:
        verbose_name = "Alım Faturası Kalemi"
        verbose_name_plural = "Alım Faturası Kalemleri"
        unique_together = ('purchase_order', 'ingredient')

    def __str__(self):
        return f"{self.quantity} {self.ingredient.unit.abbreviation} x {self.ingredient.name}"

class KDSScreen(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='kds_screens', verbose_name="İşletme")
    name = models.CharField(max_length=100, verbose_name="KDS Ekran Adı")
    slug = models.SlugField(max_length=120, unique=True, blank=True, help_text="Bu KDS ekranı için benzersiz kısa ad (URL için). Otomatik oluşturulur.")
    description = models.TextField(blank=True, null=True, verbose_name="Açıklama")
    is_active = models.BooleanField(default=True, verbose_name="Aktif Mi?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "KDS Ekranı"
        verbose_name_plural = "KDS Ekranları"
        unique_together = ('business', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.business.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.business.id}-{self.name}")
            unique_slug = base_slug
            counter = 1
            while KDSScreen.objects.filter(business=self.business, slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)


class BusinessLayout(models.Model):
    """İşletmenin masa yerleşim düzenini temsil eder."""
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='layout')
    width = models.FloatField(default=800.0, help_text="Yerleşim planı tuvalinin genişliği")
    height = models.FloatField(default=600.0, help_text="Yerleşim planı tuvalinin yüksekliği")
    background_image_url = models.URLField(max_length=1024, blank=True, null=True, verbose_name="Arka Plan Görseli URL'i")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business.name} - Yerleşim Planı"

    class Meta:
        verbose_name = "İşletme Yerleşim Planı"
        verbose_name_plural = "İşletme Yerleşim Planları"



class LayoutElement(models.Model):
    """
    İşletme yerleşim planındaki metin, şekil gibi dekoratif öğeleri temsil eder.
    """
    ELEMENT_TYPE_CHOICES = (
        ('text', 'Metin Etiketi'),
        ('shape', 'Şekil'),
    )

    SHAPE_TYPE_CHOICES = (
        ('rectangle', 'Dikdörtgen'),
        ('ellipse', 'Elips/Daire'),
        ('line', 'Çizgi'),
    )

    layout = models.ForeignKey(BusinessLayout, on_delete=models.CASCADE, related_name='elements')
    element_type = models.CharField(max_length=10, choices=ELEMENT_TYPE_CHOICES, default='text')
    
    # Konum ve Boyutlandırma
    pos_x = models.FloatField(default=50.0)
    pos_y = models.FloatField(default=50.0)
    width = models.FloatField(default=150.0)
    height = models.FloatField(default=40.0)
    rotation = models.FloatField(default=0.0, help_text="Dönme açısı (derece)")

    # İçerik ve Stil
    style_properties = models.JSONField(default=dict, help_text="Öğenin stil özelliklerini içeren JSON. Örn: {'content': 'Deniz Tarafı', 'fontSize': 16, 'color': '#FFFFFF', 'shapeType': 'rectangle'}")

    class Meta:
        verbose_name = "Yerleşim Planı Öğesi"
        verbose_name_plural = "Yerleşim Planı Öğeleri"
        ordering = ['id']

    def __str__(self):
        return f"{self.get_element_type_display()} - {self.layout.business.name}"

class Table(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='tables')
    table_number = models.PositiveIntegerField()
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # --- YENİ EKLENEN ALANLAR ---
    layout = models.ForeignKey(
        BusinessLayout, 
        on_delete=models.CASCADE, 
        related_name='tables_on_layout', 
        null=True, 
        blank=True
    )
    pos_x = models.FloatField(null=True, blank=True, verbose_name="X Koordinatı")
    pos_y = models.FloatField(null=True, blank=True, verbose_name="Y Koordinatı")
    rotation = models.FloatField(default=0.0, verbose_name="Dönme Açısı (Derece)")
    # --- YENİ ALANLAR SONU ---

    class Meta:
        unique_together = ('business', 'table_number')
        verbose_name = "Masa"
        verbose_name_plural = "Masalar"

    def __str__(self):
        return f"Masa {self.table_number} - {self.business.name}"

class Category(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories'
    )
    image = models.URLField(max_length=1024, null=True, blank=True)
    assigned_kds = models.ForeignKey(
        KDSScreen,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='categories_routed_here',
        verbose_name="Atanmış KDS Ekranı",
        help_text="Bu kategorideki ürünler hangi KDS ekranına yönlendirilecek?"
    )
    kdv_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=10.00, 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Bu kategori için varsayılan KDV oranı (%). Örn: 10.00"
    )

    class Meta:
        verbose_name = "Kategori"
        verbose_name_plural = "Kategoriler"

    def __str__(self):
        return self.name

class MenuItem(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='menu_items')
    name = models.CharField(max_length=100)
    image = models.URLField(max_length=1024, null=True, blank=True) 
    description = models.TextField(blank=True, null=True) 
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='menu_items'
    )
    is_campaign_bundle = models.BooleanField(default=False, help_text="Bu menü öğesi bir kampanya paketini mi temsil ediyor?")
    is_active = models.BooleanField(default=True, verbose_name="Menüde Aktif Mi?", help_text="Pasif ürünler yeni siparişlerde görünmez ama eski raporlarda kalır.")
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Eğer varyant yoksa veya bu bir kampanya paketi ise ürünün fiyatı."
    )
    kdv_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=10.00, 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Ürüne özel KDV oranı (%). Boş bırakılırsa kategorinin varsayılanı kullanılır."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Menü Öğesi"
        verbose_name_plural = "Menü Öğeleri"
        unique_together = ('business', 'name')
        ordering = ['name']

    def __str__(self):
        active_status = "" if self.is_active else " [Pasif]"
        return f"{self.name}{active_status} - {self.business.name}"

class MenuItemVariant(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_extra = models.BooleanField(default=False)
    image = models.URLField(max_length=1024, null=True, blank=True)

    class Meta:
        verbose_name = "Menü Varyantı"
        verbose_name_plural = "Menü Varyantları"
        unique_together = ('menu_item', 'name')
        ordering = ['name']

    def __str__(self):
        extra_str = " (Ekstra)" if self.is_extra else ""
        active_status_menu_item = "" if self.menu_item.is_active else " [Ana Ürün Pasif]"
        return f"{self.menu_item.name}{active_status_menu_item} - {self.name}{extra_str} ({self.price} TL)"

# === REÇETE MODELLERİ ===

class RecipeItem(models.Model):
    """Bir ürün varyantının reçetesini oluşturan her bir malzeme kalemini temsil eder."""
    variant = models.ForeignKey(MenuItemVariant, on_delete=models.CASCADE, related_name='recipe_items', verbose_name="Ürün Varyantı")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name='used_in_recipes', verbose_name="Malzeme")
    quantity = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Gerekli Miktar")

    class Meta:
        verbose_name = "Reçete Kalemi"
        verbose_name_plural = "Reçete Kalemleri"
        unique_together = ('variant', 'ingredient')

    def __str__(self):
        return f"{self.variant.menu_item.name} ({self.variant.name}) -> {self.quantity} {self.ingredient.unit.abbreviation} {self.ingredient.name}"

class IngredientStockMovement(models.Model):
    """Malzeme stoklarındaki tüm hareketleri kaydeder."""
    MOVEMENT_TYPES = [
        ('INITIAL', 'Başlangıç Stoku'),
        ('ADDITION', 'Stok Girişi (Alım)'),
        ('SALE', 'Satıştan Düşüm'),
        ('RETURN', 'İade'),
        ('ADJUSTMENT_IN', 'Sayım Düzeltme (Fazla)'),
        ('ADJUSTMENT_OUT', 'Sayım Düzeltme (Eksik)'),
        ('WASTAGE', 'Zayiat/Fire'),
    ]

    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity_change = models.DecimalField(max_digits=10, decimal_places=3)
    quantity_before = models.DecimalField(max_digits=10, decimal_places=3)
    quantity_after = models.DecimalField(max_digits=10, decimal_places=3)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    related_order_item = models.ForeignKey('OrderItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='ingredient_movements')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Malzeme Stok Hareketi"
        verbose_name_plural = "Malzeme Stok Hareketleri"

    def __str__(self):
        return f"{self.ingredient.name} - {self.get_movement_type_display()}: {self.quantity_change}"

class CampaignMenu(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='campaigns')
    name = models.CharField(max_length=150, verbose_name="Kampanya Adı")
    description = models.TextField(blank=True, null=True, verbose_name="Açıklama")
    image = models.URLField(max_length=1024, null=True, blank=True, verbose_name="Kampanya Görseli")
    campaign_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Kampanya Fiyatı")
    is_active = models.BooleanField(default=True, verbose_name="Aktif Mi?")
    start_date = models.DateField(null=True, blank=True, verbose_name="Başlangıç Tarihi")
    end_date = models.DateField(null=True, blank=True, verbose_name="Bitiş Tarihi")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    bundle_menu_item = models.OneToOneField(
        MenuItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='represented_campaign',
        help_text="Bu kampanyayı temsil eden özel menü öğesi."
    )

    class Meta:
        verbose_name = "Kampanya Menüsü"
        verbose_name_plural = "Kampanya Menüleri"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.campaign_price} TL) - {self.business.name}"

class CampaignMenuItem(models.Model):
    campaign_menu = models.ForeignKey(CampaignMenu, on_delete=models.CASCADE, related_name='campaign_items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, help_text="Kampanyaya dahil edilecek ana ürün.")
    variant = models.ForeignKey(MenuItemVariant, on_delete=models.CASCADE, null=True, blank=True, help_text="Eğer ürünün belirli bir varyantı kampanyaya dahilse.")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Miktar")

    class Meta:
        verbose_name = "Kampanya Menü Öğesi"
        verbose_name_plural = "Kampanya Menü Öğeleri"
        unique_together = ('campaign_menu', 'menu_item', 'variant')

    def __str__(self):
        display_name = self.menu_item.name if self.menu_item else "Silinmiş Ürün"
        if self.variant:
            display_name += f" ({self.variant.name})"
        return f"{self.quantity} x {display_name} (Kampanya: {self.campaign_menu.name})"

class Pager(models.Model):
    PAGER_STATUS_CHOICES = [
        ('available', 'Boşta'),
        ('in_use', 'Kullanımda'),
        ('charging', 'Şarj Oluyor'),
        ('low_battery', 'Düşük Batarya'),
        ('out_of_service', 'Servis Dışı'),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='pagers', verbose_name="İşletme")
    device_id = models.CharField(max_length=100, verbose_name="Cihaz ID (MAC vb.)")
    name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cihaz Adı (Takma Ad)")
    status = models.CharField(max_length=20, choices=PAGER_STATUS_CHOICES, default='available', verbose_name="Durum")
    last_status_update = models.DateTimeField(auto_now=True, verbose_name="Son Durum Güncelleme")
    current_order = models.OneToOneField(
        'Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_pager_instance',
        verbose_name="Mevcut Atanmış Sipariş"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Cihaz Notları")

    class Meta:
        unique_together = ('business', 'device_id')
        verbose_name = "Çağrı Cihazı (Pager)"
        verbose_name_plural = "Çağrı Cihazları (Pagerlar)"
        ordering = ['business', 'name', 'device_id']

    def __str__(self):
        return f"{self.name or self.device_id} ({self.get_status_display()}) - {self.business.name}"

class Order(models.Model):
    ORDER_TYPE_CHOICES = (
        ('table', 'Masa Siparişi'),
        ('takeaway', 'Takeaway Siparişi'),
    )

    STATUS_PENDING_APPROVAL = 'pending_approval'
    STATUS_APPROVED = 'approved'
    STATUS_PREPARING = 'preparing'
    STATUS_READY_FOR_PICKUP = 'ready_for_pickup'
    STATUS_READY_FOR_DELIVERY = 'ready_for_delivery'
    STATUS_REJECTED = 'rejected'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    ORDER_STATUS_CHOICES = [
        (STATUS_PENDING_APPROVAL, 'Onay Bekliyor'),
        (STATUS_APPROVED, 'Onaylandı (Mutfağa İletildi)'),
        (STATUS_PREPARING, 'Mutfakta Hazırlanıyor'),
        (STATUS_READY_FOR_PICKUP, 'Mutfakta Hazır (Garson Bekliyor)'),
        (STATUS_READY_FOR_DELIVERY, 'Teslime Hazır (Garson Aldı)'),
        (STATUS_REJECTED, 'Reddedildi'),
        (STATUS_COMPLETED, 'Tamamlandı (Ödendi)'),
        (STATUS_CANCELLED, 'İptal Edildi'),
    ]

    customer = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='orders_placed',
        null=True,
        blank=True
    )
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='business_orders')
    table = models.ForeignKey(
        Table, on_delete=models.SET_NULL, related_name='table_orders', null=True, blank=True
    )
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='table')
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Oluşturulma Tarihi (Müşteri/Personel)"
    )
    approved_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Personel tarafından onaylandığı veya mutfağa ilk iletildiği zaman.",
        verbose_name="Onaylanma/Mutfağa İletilme Tarihi"
    )
    kitchen_completed_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Siparişin TÜM kalemlerinin mutfak tarafından 'hazır' olarak işaretlendiği zaman.",
        verbose_name="Mutfakta Hazır Olma Tarihi"
    )
    picked_up_by_waiter_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Siparişin garson tarafından mutfaktan teslim alındığı zaman (müşteriye götürülmek üzere).",
        verbose_name="Garson Teslim Alma Tarihi"
    )
    delivered_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Siparişin müşteriye teslim edildiği zaman.",
        verbose_name="Müşteriye Teslim Edilme Tarihi"
    )
    is_paid = models.BooleanField(default=False, db_index=True)
    is_split_table = models.BooleanField(default=False)
    taken_by_staff = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='orders_taken_by_staff',
        null=True,
        blank=True,
        limit_choices_to=models.Q(user_type='staff') | models.Q(user_type='business_owner'),
        help_text="Siparişi alan/onaylayan garson veya işletme sahibi."
    )
    prepared_by_kitchen_staff = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='orders_prepared_in_kitchen',
        null=True,
        blank=True,
        limit_choices_to=models.Q(user_type__in=['kitchen_staff', 'staff', 'business_owner']),
        help_text="Siparişi mutfakta hazırlayan/onaylayan personel (Genel)."
    )
    status = models.CharField(
        max_length=30,
        choices=ORDER_STATUS_CHOICES,
        default=STATUS_APPROVED,
        db_index=True,
        help_text="Siparişin genel durumu."
    )
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Paket servis siparişleri için misafir menüsü QR kod linki."
    )
    total_kdv_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Toplam KDV Tutarı")
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Genel Toplam (KDV Dahil)")

    class Meta:
        verbose_name = "Sipariş"
        verbose_name_plural = "Siparişler"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self._state.adding and self.order_type == 'takeaway':
            if self.uuid is None:
                self.uuid = uuid.uuid4()
        
        if not self._state.adding and self.order_type == 'table':
            self.uuid = None

        super().save(*args, **kwargs)

    def __str__(self):
        customer_display = "Misafir"
        if self.customer:
            customer_display = self.customer.username
        elif self.customer_name:
            customer_display = self.customer_name

        status_display = self.get_status_display()
        pager_info = ""
        try:
            if hasattr(self, 'assigned_pager_instance') and self.assigned_pager_instance:
                pager_obj = self.assigned_pager_instance
                pager_info = f" (Pager: {pager_obj.name or pager_obj.device_id})"
        except Pager.DoesNotExist:
            pass
        except AttributeError:
            pass

        if self.order_type == 'table' and self.table:
            return f"Sipariş {self.id} ({customer_display}) - Masa {self.table.table_number} [{status_display}]{pager_info}"
        else:
            return f"Sipariş {self.id} ({customer_display}) - Paket [{status_display}]{pager_info}"

class OrderTableUser(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='table_users')
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Sipariş Masa Kullanıcısı"
        verbose_name_plural = "Sipariş Masa Kullanıcıları"

    def __str__(self):
        return self.name

class OrderItem(models.Model):
    KDS_ITEM_STATUS_PENDING = 'pending_kds'
    KDS_ITEM_STATUS_PREPARING = 'preparing_kds'
    KDS_ITEM_STATUS_READY = 'ready_kds'
    KDS_ITEM_STATUS_PICKED_UP = 'picked_up_kds'

    KDS_ITEM_STATUS_CHOICES = (
        (KDS_ITEM_STATUS_PENDING, 'KDS Beklemede'),
        (KDS_ITEM_STATUS_PREPARING, 'KDS Hazırlanıyor'),
        (KDS_ITEM_STATUS_READY, 'KDS Hazır'),
        (KDS_ITEM_STATUS_PICKED_UP, 'Garson Aldı'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    menu_item = models.ForeignKey(
        MenuItem,
        related_name='order_items',
        on_delete=models.PROTECT,
        help_text="Siparişe eklenen ana menü öğesi."
    )
    variant = models.ForeignKey(
        MenuItemVariant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='order_items_as_variant',
        help_text="Sipariş edilen ürünün varyantı (eğer varsa)."
    )
    quantity = models.PositiveIntegerField(default=1)
    table_user = models.CharField(max_length=100, blank=True, null=True)
    delivered = models.BooleanField(default=False, help_text="Bu kalem müşteriye teslim edildi mi?")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Bu kalemin (ekstralar dahil) KDV hariç birim fiyatı.")
    is_awaiting_staff_approval = models.BooleanField(default=False, help_text="Bu kalem misafir tarafından eklendi ve personel onayı mı bekliyor?")
    kds_status = models.CharField(
        max_length=20,
        choices=KDS_ITEM_STATUS_CHOICES,
        default=KDS_ITEM_STATUS_PENDING,
        null=True,
        blank=True,
        help_text="Bu sipariş kaleminin atandığı KDS'teki hazırlık durumu."
    )
    item_prepared_by_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='prepared_order_items',
        null=True,
        blank=True,
        limit_choices_to=models.Q(user_type__in=['kitchen_staff', 'staff', 'business_owner']),
        help_text="Bu kalemi KDS'te hazırlayan veya hazır işaretleyen personel."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    waiter_picked_up_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Kalemin garson tarafından mutfaktan alındığı zaman.",
        verbose_name="Garson Teslim Alma Zamanı (Kalem)"
    )
    kdv_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=10.00, 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Bu ürün için sipariş anındaki KDV oranı."
    )
    kdv_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Bu kalem için hesaplanan toplam KDV tutarı (birim KDV * adet)."
    )

    class Meta:
        verbose_name = "Sipariş Kalemi"
        verbose_name_plural = "Sipariş Kalemleri"

    def __str__(self):
        approval_status = " (Personel Onayı Bekliyor)" if self.is_awaiting_staff_approval else ""
        kds_display_text = self.get_kds_status_display() if self.kds_status else ""
        kds_status_info = f" [KDS: {kds_display_text}]" if kds_display_text else ""
        menu_item_name = self.menu_item.name if self.menu_item else "Bilinmeyen/Silinmiş Ürün"
        return f"{self.quantity} x {menu_item_name}{approval_status}{kds_status_info} ({self.price} TL)"
    
    def get_kds_status_display(self):
        return dict(self.KDS_ITEM_STATUS_CHOICES).get(self.kds_status, self.kds_status)

class OrderItemExtra(models.Model):
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='extras')
    variant = models.ForeignKey(MenuItemVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Sipariş Kalemi Ekstrası"
        verbose_name_plural = "Sipariş Kalemi Ekstraları"

    def __str__(self):
        return f"Ekstra: {self.variant.name} x {self.quantity}"

class Payment(models.Model):
    PAYMENT_CHOICES = [
        ('credit_card', 'Kredi Kartı'),
        ('cash', 'Nakit'),
        ('food_card', 'Yemek Kartı'),
    ]
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment_info')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ödeme"
        verbose_name_plural = "Ödemeler"

    def __str__(self):
        return f"Ödeme: Sipariş {self.order.id} - {self.get_payment_type_display()}"

class WaitingCustomer(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='waiting_customers')
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, null=True)
    party_size = models.PositiveIntegerField(default=1, help_text="Müşteri grubundaki kişi sayısı.")
    notes = models.TextField(blank=True, null=True, help_text="Müşteri ile ilgili özel notlar.")
    is_waiting = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True, help_text="Müşterinin çağrıldığı zaman.")
    seated_at = models.DateTimeField(null=True, blank=True, help_text="Müşterinin masaya oturtulduğu zaman.")

    class Meta:
        verbose_name = "Bekleyen Müşteri"
        verbose_name_plural = "Bekleyen Müşteriler"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.party_size} kişi) - Bekliyor: {self.is_waiting}"

class CreditPaymentDetails(models.Model):
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='credit_payment_details'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Veresiye Detayı"
        verbose_name_plural = "Veresiye Detayları"

    def __str__(self):
        customer_display = self.order.customer.username if self.order.customer else self.order.customer_name
        status = "Ödendi" if self.paid_at else "Ödenmedi"
        return f"Veresiye: Sipariş {self.order.id} ({customer_display or 'Bilinmiyor'}) - Durum: {status}"

class Shift(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='shifts', verbose_name="İşletme")
    name = models.CharField(max_length=100, help_text="Örn: Sabah Vardiyası, Akşam Vardiyası")
    start_time = models.TimeField(verbose_name="Başlangıç Saati")
    end_time = models.TimeField(verbose_name="Bitiş Saati")
    color = models.CharField(max_length=7, default='#3788D8', help_text="Takvimde görünecek renk kodu (Hex). Örn: #FF5733")

    class Meta:
        unique_together = ('business', 'name')
        verbose_name = "Vardiya Şablonu"
        verbose_name_plural = "Vardiya Şablonları"
        ordering = ['start_time']

    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"

class ScheduledShift(models.Model):
    staff = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='scheduled_shifts',
        limit_choices_to=models.Q(user_type__in=['staff', 'kitchen_staff']),
        verbose_name="Personel"
    )
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='scheduled_instances', verbose_name="Vardiya")
    date = models.DateField(verbose_name="Tarih")

    class Meta:
        unique_together = ('staff', 'date')
        verbose_name = "Planlanmış Vardiya"
        verbose_name_plural = "Planlanmış Vardiyalar"
        ordering = ['date', 'shift__start_time']

    def __str__(self):
        return f"{self.staff.username} - {self.date.strftime('%d/%m/%Y')} - {self.shift.name}"

class NotificationSetting(models.Model):
    """
    WebSocket üzerinden gönderilecek bildirim türlerinin aktif olup olmadığını yönetir.
    """
    # Django'daki NOTIFICATION_EVENT_TYPES listesindeki ilk değer (anahtar)
    event_type = models.CharField(
        max_length=100, 
        primary_key=True, 
        verbose_name="Bildirim Olay Tipi (Anahtar)"
    )
    is_active = models.BooleanField(
        default=True, 
        verbose_name="Aktif Mi?",
        help_text="Bu bildirim türü aktifse Redis üzerinden gönderilir. Pasif ise gönderilmez."
    )
    description = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Açıklama"
    )

    class Meta:
        verbose_name = "Bildirim Ayarı"
        verbose_name_plural = "Bildirim Ayarları"
        ordering = ['event_type']

    def __str__(self):
        status = "Aktif" if self.is_active else "Pasif"
        return f"{self.event_type} - {status}"

# === YENİ MODEL BAŞLANGICI: BusinessWebsite ===

class BusinessWebsite(models.Model):
    """İşletmeye özel web sitesi bilgileri"""
    business = models.OneToOneField(
        'Business', 
        on_delete=models.CASCADE, 
        related_name='website'
    )
    
    # Hakkımızda Bilgileri
    about_title = models.CharField(
        max_length=200, 
        default="Hakkımızda", 
        verbose_name="Hakkımızda Başlığı"
    )
    about_description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Hakkımızda Açıklaması"
    )
    about_image = models.URLField(
        max_length=1024,
        blank=True, 
        null=True, 
        verbose_name="Hakkımızda Görseli"
    )
    
    # İletişim Bilgileri
    contact_phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name="Telefon"
    )
    contact_email = models.EmailField(
        blank=True, 
        null=True, 
        verbose_name="E-posta"
    )
    contact_address = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Adres"
    )
    contact_working_hours = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Çalışma Saatleri"
    )
    
    # Harita Koordinatları
    map_latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=8, 
        blank=True, 
        null=True, 
        verbose_name="Enlem"
    )
    map_longitude = models.DecimalField(
        max_digits=11, 
        decimal_places=8, 
        blank=True, 
        null=True, 
        verbose_name="Boylam"
    )
    map_zoom_level = models.IntegerField(
        default=15, 
        verbose_name="Harita Zoom Seviyesi"
    )
    
    # SEO ve Görünüm
    website_title = models.CharField(
        max_length=200, 
        blank=True, 
        null=True, 
        verbose_name="Web Sitesi Başlığı"
    )
    website_description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Web Sitesi Açıklaması"
    )
    website_keywords = models.CharField(
        max_length=500, 
        blank=True, 
        null=True, 
        verbose_name="Anahtar Kelimeler"
    )
    
    # Sosyal Medya
    facebook_url = models.URLField(
        blank=True, 
        null=True, 
        verbose_name="Facebook URL"
    )
    instagram_url = models.URLField(
        blank=True, 
        null=True, 
        verbose_name="Instagram URL"
    )
    twitter_url = models.URLField(
        blank=True, 
        null=True, 
        verbose_name="Twitter URL"
    )
    
    # Tema ve Özelleştirme
    primary_color = models.CharField(
        max_length=7, 
        default="#3B82F6", 
        verbose_name="Ana Renk"
    )
    secondary_color = models.CharField(
        max_length=7, 
        default="#10B981", 
        verbose_name="İkincil Renk"
    )
    
    # Durum Bilgileri
    is_active = models.BooleanField(
        default=True, 
        verbose_name="Aktif mi?"
    )
    show_menu = models.BooleanField(
        default=True, 
        verbose_name="Menüyü Göster"
    )
    show_contact = models.BooleanField(
        default=True, 
        verbose_name="İletişim Bilgilerini Göster"
    )
    show_map = models.BooleanField(
        default=True, 
        verbose_name="Haritayı Göster"
    )
    
    # === YENİ ALANLAR BAŞLANGICI ===
    allow_reservations = models.BooleanField(
        default=False, 
        verbose_name="Online Rezervasyona İzin Ver"
    )
    allow_online_ordering = models.BooleanField(
        default=False, 
        verbose_name="Online Siparişe İzin Ver"
    )
    # === YENİ ALANLAR SONU ===
    
    # Zaman Damgaları
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "İşletme Web Sitesi"
        verbose_name_plural = "İşletme Web Siteleri"
        db_table = 'core_business_website'
    
    def __str__(self):
        return f"{self.business.name} - Web Sitesi"
    
    @property
    def website_url(self):
        """Web sitesi URL'ini döndürür"""
        return f"/website/{self.business.slug}/"
    
    @property
    def has_location(self):
        """Konum bilgisi var mı?"""
        return self.map_latitude is not None and self.map_longitude is not None
    
    def save(self, *args, **kwargs):
        # İlk kayıt sırasında varsayılan değerleri ayarla
        if not self.website_title:
            self.website_title = f"{self.business.name} - Resmi Web Sitesi"
        
        if not self.website_description:
            self.website_description = f"{self.business.name} restoranının resmi web sitesi. Menümüzü inceleyin ve bizimle iletişime geçin."
        
        super().save(*args, **kwargs)

# === YENİ MODEL SONU ===

# === YENİ MODEL BAŞLANGICI: Reservation ===

class Reservation(models.Model):
    """
    Müşterilerin online olarak yaptığı masa rezervasyonlarını temsil eder.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', _('Onay Bekliyor')
        CONFIRMED = 'confirmed', _('Onaylandı')
        CANCELLED = 'cancelled', _('İptal Edildi')
        SEATED = 'seated', _('Oturdu') # Müşteri geldi ve masaya yerleşti

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='reservations', verbose_name="İşletme")
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='reservations', verbose_name="Masa")
    
    customer_name = models.CharField(max_length=150, verbose_name="Müşteri Adı Soyadı")
    customer_phone = models.CharField(max_length=20, verbose_name="Müşteri Telefon")
    customer_email = models.EmailField(blank=True, null=True, verbose_name="Müşteri E-posta")
    
    reservation_time = models.DateTimeField(verbose_name="Rezervasyon Tarihi ve Saati")
    party_size = models.PositiveIntegerField(verbose_name="Kişi Sayısı")
    notes = models.TextField(blank=True, null=True, verbose_name="Özel Notlar")
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="Durum")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rezervasyon"
        verbose_name_plural = "Rezervasyonlar"
        ordering = ['-reservation_time']
        unique_together = ('table', 'reservation_time') # Aynı masaya aynı anda tek rezervasyon

    def __str__(self):
        return f"Rez. #{self.id}: {self.customer_name} - Masa {self.table.table_number} ({self.reservation_time.strftime('%d.%m %H:%M')})"

# === PERSONEL GİRİŞ-ÇIKIŞ MODELLERİ ===

class CheckInLocation(models.Model):
    """
    İşletmelerin personel giriş-çıkış noktalarını tanımlar.
    QR kod ile konum tabanlı giriş-çıkış sistemi için kullanılır.
    """
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='check_in_locations', verbose_name="İşletme")
    name = models.CharField(max_length=200, verbose_name="Lokasyon Adı")
    latitude = models.DecimalField(max_digits=10, decimal_places=8, verbose_name="Enlem")
    longitude = models.DecimalField(max_digits=11, decimal_places=8, verbose_name="Boylam")
    radius_meters = models.FloatField(default=100.0, verbose_name="Yarıçap (Metre)")
    is_active = models.BooleanField(default=True, verbose_name="Aktif Mi?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Check-in Lokasyonu"
        verbose_name_plural = "Check-in Lokasyonları"
        unique_together = ('business', 'name')
        ordering = ['name']

    def __str__(self):
        status = "Aktif" if self.is_active else "Pasif"
        return f"{self.name} - {self.business.name} ({status})"

class QRCode(models.Model):
    """
    Check-in lokasyonları için üretilen QR kodları.
    """
    location = models.ForeignKey(CheckInLocation, on_delete=models.CASCADE, related_name='qr_codes', verbose_name="Lokasyon")
    qr_data = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name="QR Kod Verisi")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Geçerlilik Bitiş Tarihi")
    is_active = models.BooleanField(default=True, verbose_name="Aktif Mi?")

    class Meta:
        verbose_name = "QR Kod"
        verbose_name_plural = "QR Kodlar"
        ordering = ['-created_at']

    def __str__(self):
        return f"QR: {self.location.name} - {str(self.qr_data)[:8]}..."


class AttendanceRecord(models.Model):
    """
    Personellerin giriş-çıkış kayıtlarını tutar.
    """
    TYPE_CHOICES = [
        ('check_in', 'Giriş'),
        ('check_out', 'Çıkış'),
    ]
    
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='attendance_records',
        verbose_name="Personel"
    )
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='attendance_records',
        verbose_name="İşletme"
    )
    check_in_location = models.ForeignKey(
        'CheckInLocation', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='attendance_records',
        verbose_name="Check-in Lokasyonu"
    )
    
    type = models.CharField(
        max_length=10, 
        choices=TYPE_CHOICES,
        verbose_name="Giriş/Çıkış Tipi"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Zaman Damgası"
    )
    
    # Konum bilgileri
    latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=8, 
        null=True, 
        blank=True,
        verbose_name="Enlem"
    )
    longitude = models.DecimalField(
        max_digits=11, 
        decimal_places=8, 
        null=True, 
        blank=True,
        verbose_name="Boylam"
    )
    
    # Ek bilgiler
    notes = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Notlar"
    )
    qr_code_data = models.UUIDField(
        null=True, 
        blank=True,
        verbose_name="QR Kod Verisi"
    )
    is_manual_entry = models.BooleanField(
        default=False,
        verbose_name="Manuel Giriş Mi?"
    )

    class Meta:
        verbose_name = "Personel Giriş-Çıkış Kaydı"
        verbose_name_plural = "Personel Giriş-Çıkış Kayıtları"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'business', '-timestamp']),
            models.Index(fields=['business', '-timestamp']),
            models.Index(fields=['type', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_type_display()} - {self.timestamp.strftime('%d.%m.%Y %H:%M')}"

    @property
    def duration_from_last_opposite_record(self):
        """Son ters tip kayıttan bu yana geçen süreyi hesaplar"""
        opposite_type = 'check_out' if self.type == 'check_in' else 'check_in'
        
        last_opposite = AttendanceRecord.objects.filter(
            user=self.user,
            business=self.business,
            type=opposite_type,
            timestamp__lt=self.timestamp
        ).order_by('-timestamp').first()
        
        if last_opposite:
            return self.timestamp - last_opposite.timestamp
        return None