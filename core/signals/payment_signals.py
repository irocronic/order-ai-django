# core/signals/payment_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F
import logging
from decimal import Decimal

# --- GÜNCELLEME: Stock ve StockMovement modelleri artık import edilmiyor ---
from ..models import (
    Payment, Ingredient, IngredientStockMovement, MenuItemVariant
)

logger = logging.getLogger(__name__)

# --- SİLİNDİ: Artık MenuItemVariant'a bağlı Stock modelini düşmüyoruz ---
# Bu fonksiyon ve mantığı tamamen kaldırıldı.
# def deduct_variant_stock(variant: MenuItemVariant, quantity_sold: int, order_item_instance):
#     ...
# --- /SİLİNDİ ---


def deduct_ingredients_for_variant(variant: MenuItemVariant, quantity_sold: int, order_item_instance):
    """Bir varyant satıldığında reçetesindeki malzemeleri stoktan düşer."""
    logger.info(f"Reçete işleme başlıyor: Varyant='{variant.name}' (ID: {variant.id}), Satılan Miktar={quantity_sold}")
    
    if not hasattr(variant, 'recipe_items'):
        logger.warning(f"Varyant '{variant.name}' (ID: {variant.id}) için reçete öğeleri bulunamadı. Malzeme düşümü atlanıyor.")
        return

    try:
        recipe_items = variant.recipe_items.select_related('ingredient', 'ingredient__unit').all()
        recipe_count = recipe_items.count()
        logger.info(f"Varyant '{variant.name}' için {recipe_count} adet reçete öğesi bulundu.")
        
        if recipe_count == 0:
            logger.warning(f"Varyant '{variant.name}' (ID: {variant.id}) için hiç reçete öğesi yok. Malzeme düşümü atlanıyor.")
            return
    except Exception as e:
        logger.error(f"Reçete öğeleri alınırken hata: {e}", exc_info=True)
        return

    for recipe_item in recipe_items:
        ingredient = recipe_item.ingredient
        quantity_to_deduct = recipe_item.quantity * Decimal(str(quantity_sold))

        logger.info(f"İşlenen malzeme: '{ingredient.name}' (ID: {ingredient.id}), Reçetedeki miktar: {recipe_item.quantity}, Düşülecek toplam: {quantity_to_deduct}")

        # Sadece stok takibi aktifse envanterden düş
        if not ingredient.track_stock:
            logger.info(f"Envanter Düşümü Atlandı (Takip Dışı): '{ingredient.name}'")
            continue

        try:
            with transaction.atomic():
                ingredient_to_update = Ingredient.objects.select_for_update().get(id=ingredient.id)
                
                original_quantity = ingredient_to_update.stock_quantity
                new_quantity = max(Decimal('0.000'), original_quantity - quantity_to_deduct)

                supplier_email = None
                if hasattr(ingredient_to_update, 'supplier') and ingredient_to_update.supplier:
                    supplier_email = ingredient_to_update.supplier.email

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
                
                ingredient_to_update.stock_quantity = new_quantity
                
                update_fields = ['stock_quantity']
                if (ingredient_to_update.alert_threshold is not None and
                    new_quantity <= ingredient_to_update.alert_threshold and
                    not ingredient_to_update.low_stock_notification_sent and
                    supplier_email):
                    
                    from ..tasks import send_low_stock_notification_email_task
                    send_low_stock_notification_email_task.delay(ingredient_to_update.id)
                    ingredient_to_update.low_stock_notification_sent = True
                    update_fields.append('low_stock_notification_sent')
                    logger.info(f"DÜŞÜK STOK: '{ingredient_to_update.name}' için tedarikçiye e-posta görevi kuyruğa alındı.")

                elif (ingredient_to_update.alert_threshold is not None and
                      new_quantity > ingredient_to_update.alert_threshold and
                      ingredient_to_update.low_stock_notification_sent):
                    
                    ingredient_to_update.low_stock_notification_sent = False
                    update_fields.append('low_stock_notification_sent')
                    logger.info(f"STOK YENİLENDİ: '{ingredient_to_update.name}' için düşük stok bildirim bayrağı sıfırlandı.")
                    
                ingredient_to_update.save(update_fields=update_fields)

                logger.info(
                    f"Malzeme Stoğu Düşürüldü: '{ingredient.name}' (ID: {ingredient.id}), "
                    f"Miktar: {quantity_to_deduct} {ingredient.unit.abbreviation}. "
                    f"Sipariş Kalemi: {order_item_instance.id}"
                )

        except Ingredient.DoesNotExist:
            logger.error(f"MALZEME STOK DÜŞME HATASI: Reçetedeki malzeme (ID: {ingredient.id}) bulunamadı.")
        except Exception as e:
            logger.error(f"MALZEME STOK DÜŞME HATASI: Malzeme '{ingredient.name}' düşülürken beklenmedik hata: {e}", exc_info=True)

    logger.info(f"Reçete işleme tamamlandı: Varyant='{variant.name}' (ID: {variant.id})")


@receiver(post_save, sender=Payment)
@transaction.atomic
def handle_payment_and_stock_deduction(sender, instance: Payment, created: bool, **kwargs):
    """
    Bir ödeme kaydı oluşturulduğunda, siparişteki ürünlere göre SADECE malzeme (reçete)
    stoklarını düşer.
    """
    if not created or not instance.order or not instance.order.is_paid:
        logger.info(f"Ödeme sinyali atlandı: Payment ID={instance.id}, Created={created}, Order={instance.order}, Is_Paid={instance.order.is_paid if instance.order else 'N/A'}")
        return
        
    logger.info(f"SİNYAL (Ödeme): Stok düşümü tetiklendi. Payment ID: {instance.id}, Order ID: {instance.order.id}")
    order = instance.order

    try:
        order_items = order.order_items.select_related(
            'menu_item', 
            'variant', 
            'menu_item__represented_campaign'
        ).prefetch_related(
            'extras__variant__recipe_items__ingredient__unit', 
            'variant__recipe_items__ingredient__unit'
        ).all()
        
        order_items_count = order_items.count()
        logger.info(f"Sipariş #{order.id} için {order_items_count} adet sipariş kalemi bulundu.")
        
        if order_items_count == 0:
            logger.warning(f"Sipariş #{order.id} için hiç sipariş kalemi bulunamadı. Stok düşümü atlanıyor.")
            return

        for order_item in order_items:
            logger.info(f"İşlenen sipariş kalemi: '{order_item.menu_item.name}' x{order_item.quantity}")
            
            # Durum 1: Satılan ürün bir kampanya paketi ise
            if order_item.menu_item.is_campaign_bundle and hasattr(order_item.menu_item, 'represented_campaign'):
                logger.info(f"Kampanya paketi tespit edildi: '{order_item.menu_item.name}'")
                campaign = order_item.menu_item.represented_campaign
                if not campaign:
                    logger.warning(f"Kampanya paketi '{order_item.menu_item.name}' için kampanya bulunamadı.")
                    continue
                
                for campaign_item in campaign.campaign_items.select_related('variant').all():
                    if campaign_item.variant:
                        total_quantity_sold = order_item.quantity * campaign_item.quantity
                        logger.info(f"Kampanya öğesi işleniyor: '{campaign_item.variant.name}' x{total_quantity_sold}")
                        deduct_ingredients_for_variant(campaign_item.variant, total_quantity_sold, order_item)
                        # --- SİLİNDİ: deduct_variant_stock çağrısı kaldırıldı ---

            # Durum 2: Satılan ürün normal bir ürün ise (varyantı olan)
            elif order_item.variant:
                logger.info(f"Normal ürün işleniyor: '{order_item.variant.name}' x{order_item.quantity}")
                deduct_ingredients_for_variant(order_item.variant, order_item.quantity, order_item)
                # --- SİLİNDİ: deduct_variant_stock çağrısı kaldırıldı ---
            else:
                logger.warning(f"Sipariş kalemi '{order_item.menu_item.name}' için varyant bulunamadı.")

            # Durum 3: Satılan ürünün ekstraları varsa, onların da stoğunu düş
            try:
                extras_count = order_item.extras.count()
                if extras_count > 0:
                    logger.info(f"{extras_count} adet ekstra bulundu.")
                    for extra in order_item.extras.select_related('variant').all():
                        total_extra_quantity_sold = order_item.quantity * extra.quantity
                        logger.info(f"Ekstra işleniyor: '{extra.variant.name}' x{total_extra_quantity_sold}")
                        deduct_ingredients_for_variant(extra.variant, total_extra_quantity_sold, order_item)
                        # --- SİLİNDİ: deduct_variant_stock çağrısı kaldırıldı ---
            except Exception as extra_error:
                logger.error(f"Ekstra işlenirken hata: {extra_error}")
        
        logger.info(f"TÜMÜ TAMAMLANDI: Sipariş #{order.id} için tüm stok düşümleri ve e-posta kontrolleri tamamlandı.")
        
    except Exception as e:
        logger.error(f"Sipariş işlenirken genel hata: {e}", exc_info=True)