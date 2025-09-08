# core/signals/payment_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F
import logging

# === GÜNCELLENMİŞ IMPORTLAR ===
from ..models import (
    Payment, Ingredient, IngredientStockMovement, MenuItemVariant,
    Stock, StockMovement
)
# ==============================

logger = logging.getLogger(__name__)

# ==================== YENİ FONKSİYON BAŞLANGICI ====================
def deduct_variant_stock(variant: MenuItemVariant, quantity_sold: int, order_item_instance):
    """
    Bir varyant satıldığında, onun ana stok kalemini (Stock modeli) düşer.
    Bu, "Stok Yönetimi" ekranındaki stokları yönetir.
    """
    try:
        # Yarış koşullarını (race condition) önlemek için satırı kilitle
        stock_to_update = Stock.objects.select_for_update().get(variant=variant)

        # Sadece stok takibi aktifse işlem yap
        if not stock_to_update.track_stock:
            logger.info(f"Ana Stok Düşümü Atlandı (Takip Dışı): '{variant.name}'")
            return

        original_quantity = stock_to_update.quantity
        
        # Stoktan düşülecek miktar, mevcut stoktan fazlaysa stoğu sıfırla.
        new_quantity_val = max(0, original_quantity - quantity_sold)

        # Stok hareketini kaydet
        StockMovement.objects.create(
            stock=stock_to_update,
            variant=variant,
            movement_type='SALE',
            quantity_change=-quantity_sold,
            quantity_before=original_quantity,
            quantity_after=new_quantity_val, # Hesaplanan yeni değeri kullan
            user=order_item_instance.order.taken_by_staff,
            description=f"Sipariş #{order_item_instance.order.id} ile satış.",
            related_order=order_item_instance.order
        )
        
        # Stok miktarını F expression ile atomik olarak güncelle
        stock_to_update.quantity = F('quantity') - quantity_sold
        stock_to_update.save(update_fields=['quantity'])
        
        # Negatif stok olmaması için stoğu tekrar kontrol et ve gerekirse düzelt
        stock_to_update.refresh_from_db()
        if stock_to_update.quantity < 0:
            stock_to_update.quantity = 0
            stock_to_update.save(update_fields=['quantity'])

        logger.info(
            f"Ana Stok Düşüldü: '{variant.name}' (ID: {variant.id}), "
            f"Miktar: {quantity_sold}. "
            f"Sipariş Kalemi: {order_item_instance.id}"
        )

    except Stock.DoesNotExist:
        logger.warning(f"ANA STOK DÜŞME HATASI: Varyant '{variant.name}' (ID: {variant.id}) için stok kaydı bulunamadı.")
    except Exception as e:
        logger.error(f"ANA STOK DÜŞME HATASI: Varyant '{variant.name}' düşülürken beklenmedik hata: {e}", exc_info=True)
# ==================== YENİ FONKSİYON SONU ======================


def deduct_ingredients_for_variant(variant: MenuItemVariant, quantity_sold: int, order_item_instance):
    """Bir varyant satıldığında reçetesindeki malzemeleri stoktan düşer."""
    if not hasattr(variant, 'recipe_items'):
        return

    for recipe_item in variant.recipe_items.select_related('ingredient', 'ingredient__unit').all():
        ingredient = recipe_item.ingredient
        quantity_to_deduct = recipe_item.quantity * quantity_sold

        try:
            ingredient_to_update = Ingredient.objects.select_for_update().get(id=ingredient.id)
            
            original_quantity = ingredient_to_update.stock_quantity
            new_quantity = original_quantity - quantity_to_deduct

            IngredientStockMovement.objects.create(
                ingredient=ingredient_to_update,
                movement_type='SALE',
                quantity_change=-quantity_to_deduct,
                quantity_before=original_quantity,
                quantity_after=new_quantity,
                user=order_item_instance.order.taken_by_staff,
                description=f"Sipariş #{order_item_instance.order.id} ile satış.",
                related_order_item=order_item_instance
            )
            
            ingredient_to_update.stock_quantity = F('stock_quantity') - quantity_to_deduct
            ingredient_to_update.save(update_fields=['stock_quantity'])

            logger.info(
                f"Malzeme Stoğu Düşüldü: '{ingredient.name}' (ID: {ingredient.id}), "
                f"Miktar: {quantity_to_deduct} {ingredient.unit.abbreviation}. "
                f"Sipariş Kalemi: {order_item_instance.id}"
            )

        except Ingredient.DoesNotExist:
            logger.error(f"MALZEME STOK DÜŞME HATASI: Reçetedeki malzeme (ID: {ingredient.id}) bulunamadı.")
        except Exception as e:
            logger.error(f"MALZEME STOK DÜŞME HATASI: Malzeme '{ingredient.name}' düşülürken beklenmedik hata: {e}", exc_info=True)


# ==================== GÜNCELLENMİŞ SİNYAL FONKSİYONU ====================
@receiver(post_save, sender=Payment)
@transaction.atomic
def handle_payment_and_stock_deduction(sender, instance: Payment, created: bool, **kwargs):
    """
    Bir ödeme kaydı oluşturulduğunda, siparişteki ürünlere göre hem malzeme (reçete)
    hem de ana ürün (varyant) stoklarını düşer.
    """
    if not created or not instance.order or not instance.order.is_paid:
        return
        
    logger.info(f"SİNYAL (Ödeme): Stok düşümü tetiklendi. Payment ID: {instance.id}")
    order = instance.order

    for order_item in order.order_items.select_related(
        'menu_item', 
        'variant', 
        'menu_item__represented_campaign'
    ).prefetch_related(
        'extras__variant__recipe_items__ingredient__unit', 
        'variant__recipe_items__ingredient__unit'
    ).all():
        
        # Durum 1: Satılan ürün bir kampanya paketi ise
        if order_item.menu_item.is_campaign_bundle and hasattr(order_item.menu_item, 'represented_campaign'):
            campaign = order_item.menu_item.represented_campaign
            if not campaign:
                continue
            
            for campaign_item in campaign.campaign_items.select_related('variant').all():
                if campaign_item.variant:
                    total_quantity_sold = order_item.quantity * campaign_item.quantity
                    # Malzeme stoğunu düş (reçete sistemi)
                    deduct_ingredients_for_variant(campaign_item.variant, total_quantity_sold, order_item)
                    # === YENİ: Ana ürün stoğunu düş ===
                    deduct_variant_stock(campaign_item.variant, total_quantity_sold, order_item)

        # Durum 2: Satılan ürün normal bir ürün ise (varyantı olan)
        elif order_item.variant:
            # Malzeme stoğunu düş (reçete sistemi)
            deduct_ingredients_for_variant(order_item.variant, order_item.quantity, order_item)
            # === YENİ: Ana ürün stoğunu düş ===
            deduct_variant_stock(order_item.variant, order_item.quantity, order_item)

        # Durum 3: Satılan ürünün ekstraları varsa, onların da stoğunu düş
        for extra in order_item.extras.select_related('variant').all():
            total_extra_quantity_sold = order_item.quantity * extra.quantity
            # Malzeme stoğunu düş (reçete sistemi)
            deduct_ingredients_for_variant(extra.variant, total_extra_quantity_sold, order_item)
            # === YENİ: Ana ürün stoğunu düş ===
            deduct_variant_stock(extra.variant, total_extra_quantity_sold, order_item)