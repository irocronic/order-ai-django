# core/signals/payment_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F
import logging
from decimal import Decimal

from ..models import (
    Payment, Ingredient, IngredientStockMovement, MenuItemVariant,
    Stock, StockMovement
)
# E-posta görevini tetiklemek için tasks.py dosyasını import ediyoruz
from ..tasks import send_low_stock_notification_email_task

logger = logging.getLogger(__name__)

def deduct_variant_stock(variant: MenuItemVariant, quantity_sold: int, order_item_instance):
    """
    Bir varyant satıldığında, onun ana stok kalemini (Stock modeli) düşer.
    HATA DÜZELTMESİ: Stok miktarı veritabanına kaydedilmeden önce Python içinde
    hesaplanır, böylece negatif değere düşmesi engellenir.
    """
    try:
        # Yarış koşullarını (race condition) önlemek için satırı kilitle
        stock_to_update = Stock.objects.select_for_update().get(variant=variant)

        # Sadece stok takibi aktifse işlem yap
        if not stock_to_update.track_stock:
            logger.info(f"Ana Stok Düşümü Atlandı (Takip Dışı): '{variant.name}'")
            return

        original_quantity = stock_to_update.quantity
        
        # === KESİN ÇÖZÜM: Yeni miktar veritabanına yazmadan ÖNCE hesaplanır ===
        new_quantity_val = max(0, original_quantity - quantity_sold)
        # =====================================================================

        StockMovement.objects.create(
            stock=stock_to_update,
            variant=variant,
            movement_type='SALE',
            quantity_change=-quantity_sold,
            quantity_before=original_quantity,
            quantity_after=new_quantity_val,
            user=order_item_instance.order.taken_by_staff,
            description=f"Sipariş #{order_item_instance.order.id} ile satış.",
            related_order=order_item_instance.order
        )
        
        # === KESİN ÇÖZÜM: F() ifadesi yerine hesaplanmış değer kullanılır ===
        stock_to_update.quantity = new_quantity_val
        stock_to_update.save(update_fields=['quantity'])
        # =====================================================================

        logger.info(
            f"Ana Stok Düşüldü: '{variant.name}' (ID: {variant.id}), "
            f"Miktar: {quantity_sold}. "
            f"Sipariş Kalemi: {order_item_instance.id}"
        )

    except Stock.DoesNotExist:
        logger.warning(f"ANA STOK DÜŞME HATASI: Varyant '{variant.name}' (ID: {variant.id}) için stok kaydı bulunamadı.")
    except Exception as e:
        logger.error(f"ANA STOK DÜŞME HATASI: Varyant '{variant.name}' düşülürken beklenmedik hata: {e}", exc_info=True)


def deduct_ingredients_for_variant(variant: MenuItemVariant, quantity_sold: int, order_item_instance):
    """Bir varyant satıldığında reçetesindeki malzemeleri stoktan düşer."""
    # === YENİ: Detaylı başlangıç logu ===
    logger.info(f"🔄 Reçete işleme başlıyor: Varyant='{variant.name}' (ID: {variant.id}), Satılan Miktar={quantity_sold}")
    
    if not hasattr(variant, 'recipe_items'):
        logger.warning(f"⚠️ Varyant '{variant.name}' (ID: {variant.id}) için reçete öğeleri bulunamadı. Malzeme düşümü atlanıyor.")
        return

    # === YENİ: Reçete öğe sayısı kontrolü ===
    recipe_items = variant.recipe_items.select_related('ingredient', 'ingredient__unit', 'ingredient__supplier').all()
    recipe_count = recipe_items.count()
    logger.info(f"📋 Varyant '{variant.name}' için {recipe_count} adet reçete öğesi bulundu.")
    
    if recipe_count == 0:
        logger.warning(f"⚠️ Varyant '{variant.name}' (ID: {variant.id}) için hiç reçete öğesi yok. Malzeme düşümü atlanıyor.")
        return

    for recipe_item in recipe_items:
        ingredient = recipe_item.ingredient
        quantity_to_deduct = recipe_item.quantity * Decimal(str(quantity_sold))

        # === YENİ: İşlenen malzeme detay logu ===
        logger.info(f"🧾 İşlenen malzeme: '{ingredient.name}' (ID: {ingredient.id}), Reçetedeki miktar: {recipe_item.quantity}, Düşülecek toplam: {quantity_to_deduct}")

        try:
            ingredient_to_update = Ingredient.objects.select_for_update().get(id=ingredient.id)
            
            original_quantity = ingredient_to_update.stock_quantity
            
            # Malzeme stoğunun da eksiye düşmemesini garantile
            new_quantity = max(Decimal('0.000'), original_quantity - quantity_to_deduct)

            # === YENİ: Detaylı malzeme durumu logu ===
            logger.info(
                f"📊 MALZEME DETAY: '{ingredient_to_update.name}' - "
                f"Önceki Stok: {original_quantity}, "
                f"Sonraki Stok: {new_quantity}, "
                f"Alert Eşiği: {ingredient_to_update.alert_threshold}, "
                f"Tedarikçi: {ingredient_to_update.supplier.name if ingredient_to_update.supplier else 'Atanmamış'}, "
                f"Tedarikçi E-posta: {ingredient_to_update.supplier.email if ingredient_to_update.supplier else 'Yok'}"
            )

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
            
            # F() yerine hesaplanmış değeri kullanarak güncelle
            ingredient_to_update.stock_quantity = new_quantity
            ingredient_to_update.save(update_fields=['stock_quantity'])

            # === GELİŞTİRİLMİŞ: Düşük stok kontrolü ve e-posta tetikleme ===
            ingredient_to_update.refresh_from_db()  # En güncel stok miktarını al
            
            logger.info(
                f"🔍 ALERT KONTROLÜ: Malzeme='{ingredient_to_update.name}', "
                f"Mevcut Stok={ingredient_to_update.stock_quantity}, "
                f"Alert Threshold={ingredient_to_update.alert_threshold}, "
                f"Supplier={ingredient_to_update.supplier}, "
                f"Supplier Email={ingredient_to_update.supplier.email if ingredient_to_update.supplier else 'Yok'}"
            )
            
            # Kapsamlı koşul kontrolü
            if ingredient_to_update.alert_threshold is not None:
                if ingredient_to_update.stock_quantity <= ingredient_to_update.alert_threshold:
                    if ingredient_to_update.supplier is not None:
                        if ingredient_to_update.supplier.email:
                            logger.info(f"✅ DÜŞÜK STOK TESPİT EDİLDİ: '{ingredient_to_update.name}' - E-posta task başlatılıyor.")
                            try:
                                task_result = send_low_stock_notification_email_task.delay(ingredient_to_update.id)
                                logger.info(f"📧 E-posta task kuyruğa alındı. Task ID: {task_result.id}")
                            except Exception as task_error:
                                logger.error(f"❌ E-posta task başlatılırken hata: {task_error}", exc_info=True)
                        else:
                            logger.warning(f"⚠️ Malzeme '{ingredient_to_update.name}' tedarikçisinin e-posta adresi yok. E-posta gönderilemedi.")
                    else:
                        logger.warning(f"⚠️ Malzeme '{ingredient_to_update.name}' için tedarikçi atanmamış. E-posta gönderilemedi.")
                else:
                    logger.info(f"ℹ️ Malzeme '{ingredient_to_update.name}' henüz alert eşiğini aşmadı. (Mevcut: {ingredient_to_update.stock_quantity}, Eşik: {ingredient_to_update.alert_threshold})")
            else:
                logger.warning(f"⚠️ Malzeme '{ingredient_to_update.name}' için alert_threshold ayarlanmamış. E-posta bildirimi gönderilmedi.")
            # =======================================================

            logger.info(
                f"✅ Malzeme Stoğu Düşürüldü: '{ingredient.name}' (ID: {ingredient.id}), "
                f"Miktar: {quantity_to_deduct} {ingredient.unit.abbreviation}. "
                f"Sipariş Kalemi: {order_item_instance.id}"
            )

        except Ingredient.DoesNotExist:
            logger.error(f"❌ MALZEME STOK DÜŞME HATASI: Reçetedeki malzeme (ID: {ingredient.id}) bulunamadı.")
        except Exception as e:
            logger.error(f"❌ MALZEME STOK DÜŞME HATASI: Malzeme '{ingredient.name}' düşülürken beklenmedik hata: {e}", exc_info=True)

    # === YENİ: Reçete işleme tamamlandı logu ===
    logger.info(f"🏁 Reçete işleme tamamlandı: Varyant='{variant.name}' (ID: {variant.id})")


@receiver(post_save, sender=Payment)
@transaction.atomic
def handle_payment_and_stock_deduction(sender, instance: Payment, created: bool, **kwargs):
    """
    Bir ödeme kaydı oluşturulduğunda, siparişteki ürünlere göre hem malzeme (reçete)
    hem de ana ürün (varyant) stoklarını düşer.
    """
    if not created or not instance.order or not instance.order.is_paid:
        # === YENİ: Atlanma durumu detaylı logu ===
        logger.info(f"💸 Ödeme sinyali atlandı: Payment ID={instance.id}, Created={created}, Order={instance.order}, Is_Paid={instance.order.is_paid if instance.order else 'N/A'}")
        return
        
    logger.info(f"💰 SİNYAL (Ödeme): Stok düşümü tetiklendi. Payment ID: {instance.id}, Order ID: {instance.order.id}")
    order = instance.order

    # === YENİ: Sipariş öğeleri sayısı kontrolü ===
    order_items = order.order_items.select_related(
        'menu_item', 
        'variant', 
        'menu_item__represented_campaign'
    ).prefetch_related(
        'extras__variant__recipe_items__ingredient__unit__supplier', 
        'variant__recipe_items__ingredient__unit__supplier'
    ).all()
    
    order_items_count = order_items.count()
    logger.info(f"🛒 Sipariş #{order.id} için {order_items_count} adet sipariş kalemi bulundu.")
    
    if order_items_count == 0:
        logger.warning(f"⚠️ Sipariş #{order.id} için hiç sipariş kalemi bulunamadı. Stok düşümü atlanıyor.")
        return

    for order_item in order_items:
        logger.info(f"🔄 İşlenen sipariş kalemi: '{order_item.menu_item.name}' x{order_item.quantity}")
        
        # Durum 1: Satılan ürün bir kampanya paketi ise
        if order_item.menu_item.is_campaign_bundle and hasattr(order_item.menu_item, 'represented_campaign'):
            logger.info(f"🎁 Kampanya paketi tespit edildi: '{order_item.menu_item.name}'")
            campaign = order_item.menu_item.represented_campaign
            if not campaign:
                logger.warning(f"⚠️ Kampanya paketi '{order_item.menu_item.name}' için kampanya bulunamadı.")
                continue
            
            for campaign_item in campaign.campaign_items.select_related('variant').all():
                if campaign_item.variant:
                    total_quantity_sold = order_item.quantity * campaign_item.quantity
                    logger.info(f"🎁 Kampanya öğesi işleniyor: '{campaign_item.variant.name}' x{total_quantity_sold}")
                    deduct_ingredients_for_variant(campaign_item.variant, total_quantity_sold, order_item)
                    deduct_variant_stock(campaign_item.variant, total_quantity_sold, order_item)

        # Durum 2: Satılan ürün normal bir ürün ise (varyantı olan)
        elif order_item.variant:
            logger.info(f"🍽️ Normal ürün işleniyor: '{order_item.variant.name}' x{order_item.quantity}")
            deduct_ingredients_for_variant(order_item.variant, order_item.quantity, order_item)
            deduct_variant_stock(order_item.variant, order_item.quantity, order_item)
        else:
            logger.warning(f"⚠️ Sipariş kalemi '{order_item.menu_item.name}' için varyant bulunamadı.")

        # Durum 3: Satılan ürünün ekstraları varsa, onların da stoğunu düş
        extras_count = order_item.extras.count()
        if extras_count > 0:
            logger.info(f"➕ {extras_count} adet ekstra bulundu.")
            for extra in order_item.extras.select_related('variant').all():
                total_extra_quantity_sold = order_item.quantity * extra.quantity
                logger.info(f"➕ Ekstra işleniyor: '{extra.variant.name}' x{total_extra_quantity_sold}")
                deduct_ingredients_for_variant(extra.variant, total_extra_quantity_sold, order_item)
                deduct_variant_stock(extra.variant, total_extra_quantity_sold, order_item)
    
    # === YENİ: Tüm işlemler tamamlandı logu ===
    logger.info(f"🏁 TÜMÜ TAMAMLANDI: Sipariş #{order.id} için tüm stok düşümleri ve e-posta kontrolleri tamamlandı.")