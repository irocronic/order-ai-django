# templates/models.py

from django.db import models

class CategoryTemplate(models.Model):
    name = models.CharField(max_length=100, verbose_name="Şablon Adı")
    icon_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Flutter İkon Adı", help_text="Örn: 'local_dining', 'local_bar'")
    language = models.CharField(max_length=5, default='tr', verbose_name="Dil Kodu", help_text="Örn: 'tr', 'en'")
    
    class Meta:
        verbose_name = "Kategori Şablonu"
        verbose_name_plural = "Kategori Şablonları"
        ordering = ['name']
        unique_together = ('name', 'language')

    def __str__(self):
        return f"{self.name} ({self.language.upper()})"

class MenuItemTemplate(models.Model):
    category_template = models.ForeignKey(
        CategoryTemplate, 
        on_delete=models.CASCADE, 
        related_name='menu_item_templates',
        verbose_name="Kategori Şablonu"
    )
    name = models.CharField(max_length=100, verbose_name="Ürün Adı Şablonu")
    language = models.CharField(max_length=5, default='tr', verbose_name="Dil Kodu")

    class Meta:
        verbose_name = "Menü Ürünü Şablonu"
        verbose_name_plural = "Menü Ürünü Şablonları"
        ordering = ['name']
        unique_together = ('category_template', 'name', 'language')

    def __str__(self):
        return f"{self.name} ({self.category_template.name} - {self.language.upper()})"

# === YENİ MODEL: Varyant Şablonları ===
class VariantTemplate(models.Model):
    category_template = models.ForeignKey(
        CategoryTemplate,
        on_delete=models.CASCADE,
        related_name='variant_templates',
        verbose_name="Kategori Şablonu"
    )
    name = models.CharField(max_length=100, verbose_name="Varyant Adı")
    price_multiplier = models.DecimalField(
        max_digits=4, 
        decimal_places=2, 
        default=1.0,
        verbose_name="Fiyat Çarpanı",
        help_text="Ana ürün fiyatı ile çarpılacak değer (örn: 1.3 = %30 artış)"
    )
    icon_name = models.CharField(
        max_length=100, 
        verbose_name="Flutter İkon Adı",
        help_text="Örn: 'restaurant', 'local_cafe'"
    )
    language = models.CharField(max_length=5, default='tr', verbose_name="Dil Kodu")
    display_order = models.PositiveIntegerField(default=0, verbose_name="Sıra")
    
    class Meta:
        verbose_name = "Varyant Şablonu"
        verbose_name_plural = "Varyant Şablonları"
        ordering = ['category_template', 'display_order', 'name']
        unique_together = ('category_template', 'name', 'language')
    
    def __str__(self):
        return f"{self.name} ({self.category_template.name} - {self.language.upper()})"