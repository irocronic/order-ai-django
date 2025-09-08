# core/signals/payment_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F  # <-- HATA BURADA DÜZELTİLDİ
import logging

# Proje içi importlar
from ..models import Payment, Ingredient, IngredientStockMovement, MenuItemVariant

logger = logging.getLogger(__name__)

def deduct_ingredients_for_variant(variant: MenuItemVariant, quantity_sold: int, order_item_instance):
    """Bir varyant satıldığında reçetesindeki malzemeleri stoktan düşer."""
    if not hasattr(variant, 'recipe_items'):
        return

    # İlgili reçete kalemlerini ve malzemelerini veritabanından tek seferde çek
    for recipe_item in variant.recipe_items.select_related('ingredient', 'ingredient__unit').all():
        ingredient = recipe_item.ingredient
        # Satılan ürün adedi ile reçetedeki gerekli miktarı çarp
        quantity_to_deduct = recipe_item.quantity * quantity_sold

        try:
            # Yarış koşullarını (race condition) önlemek için satırı kilitle
            ingredient_to_update = Ingredient.objects.select_for_update().get(id=ingredient.id)
            
            original_quantity = ingredient_to_update.stock_quantity
            new_quantity = original_quantity - quantity_to_deduct

            # Stok hareketini kaydet
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
            
            # Atomik güncelleme ile stok miktarını düş
            ingredient_to_update.stock_quantity = F('stock_quantity') - quantity_to_deduct
            ingredient_to_update.save(update_fields=['stock_quantity'])

            logger.info(
                f"Malzeme Düşüldü: '{ingredient.name}' (ID: {ingredient.id}), "
                f"Miktar: {quantity_to_deduct} {ingredient.unit.abbreviation}. "
                f"Sipariş Kalemi: {order_item_instance.id}"
            )

        except Ingredient.DoesNotExist:
            logger.error(f"STOK DÜŞME HATASI: Reçetedeki malzeme (ID: {ingredient.id}) bulunamadı.")
        except Exception as e:
            logger.error(f"STOK DÜŞME HATASI: Malzeme '{ingredient.name}' düşülürken beklenmedik hata: {e}", exc_info=True)


@receiver(post_save, sender=Payment)
@transaction.atomic
def handle_payment_and_ingredient_deduction(sender, instance: Payment, created: bool, **kwargs):
    """
    Bir ödeme kaydı oluşturulduğunda ve sipariş ödenmiş olarak işaretlendiğinde,
    siparişteki ürünlerin reçetelerine göre ilgili malzemelerin stoklarını düşer.
    """
    # Sadece yeni oluşturulmuş bir ödeme ise ve ilişkili sipariş ödenmişse devam et
    if not created or not instance.order or not instance.order.is_paid:
        return
        
    logger.info(f"SİNYAL (Ödeme): Malzeme bazlı stok düşümü tetiklendi. Payment ID: {instance.id}")
    order = instance.order

    # Siparişteki tüm kalemleri ve ilişkili verileri (kampanya, reçete vb.) verimli bir şekilde çek
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
            
            # Kampanyanın içindeki her bir ürün için stok düşümü yap
            for campaign_item in campaign.campaign_items.select_related('variant').all():
                if campaign_item.variant:
                    # Satılan kampanya adedi * kampanyanın içindeki ürün adedi
                    total_quantity_sold = order_item.quantity * campaign_item.quantity
                    deduct_ingredients_for_variant(campaign_item.variant, total_quantity_sold, order_item)

        # Durum 2: Satılan ürün normal bir ürün ise (varyantı olan)
        elif order_item.variant:
            deduct_ingredients_for_variant(order_item.variant, order_item.quantity, order_item)

        # Durum 3: Satılan ürünün ekstraları varsa, onların da stoğunu düş
        for extra in order_item.extras.select_related('variant').all():
            # Satılan ana ürün adedi * ekstra ürün adedi
            total_extra_quantity_sold = order_item.quantity * extra.quantity
            deduct_ingredients_for_variant(extra.variant, total_extra_quantity_sold, order_item)