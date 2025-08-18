# core/signals/payment_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F
import logging

# Proje içi importlar
from ..models import Order, Payment, Stock, StockMovement

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Payment)
@transaction.atomic
def handle_payment_and_stock_deduction(sender, instance: Payment, created: bool, **kwargs):
    logger.info(f"SİNYAL (Ödeme): handle_payment_and_stock_deduction tetiklendi. Payment ID: {instance.id}, Created: {created}")

    if created and instance.order and instance.order.is_paid:
        order = instance.order
        logger.info(f"SİNYAL (Stok Düşümü): Koşullar sağlandı. Order ID: {order.id}, Sipariş Durumu: {order.status}. Stok düşürme başlıyor.")
        
        if order.status != Order.STATUS_COMPLETED:
            logger.warning(
                f"SİNYAL (Stok Düşümü Uyarı): Sipariş #{order.id} ödenmiş ancak durumu '{Order.STATUS_COMPLETED}' değil (Mevcut: '{order.status}'). Yine de stok düşülüyor."
            )

        for order_item in order.order_items.all().select_related(
            'menu_item__business', 'menu_item__represented_campaign', 
            'menu_item__represented_campaign__business', 'variant'
        ):
            if order_item.menu_item.is_campaign_bundle and hasattr(order_item.menu_item, 'represented_campaign') and order_item.menu_item.represented_campaign:
                campaign = order_item.menu_item.represented_campaign
                if campaign and campaign.business == order.business: 
                    logger.info(f"SİNYAL (Stok Düşümü - Kampanya): '{campaign.name}' (Sipariş Kalemi ID: {order_item.id}) için iç ürünlerin stoğu düşülüyor.")
                    campaign_bundle_quantity = order_item.quantity

                    for campaign_item_instance in campaign.campaign_items.select_related('menu_item', 'variant', 'variant__menu_item__business').all():
                        variant_to_deduct_from_campaign = campaign_item_instance.variant
                        
                        if not variant_to_deduct_from_campaign and campaign_item_instance.menu_item:
                            non_extra_variants = campaign_item_instance.menu_item.variants.filter(is_extra=False)
                            if non_extra_variants.count() == 1:
                                variant_to_deduct_from_campaign = non_extra_variants.first()
                            else:
                                logger.warning(f"SİNYAL (Kampanya Stok Düşümü UYARI): Kampanya '{campaign.name}' içindeki '{campaign_item_instance.menu_item.name}' ürünü için uygun tekil varyant bulunamadı. Stok düşümü atlanıyor.")
                                continue
                        
                        if variant_to_deduct_from_campaign:
                            if variant_to_deduct_from_campaign.menu_item.business != order.business:
                                logger.error(f"SİNYAL (Kampanya Stok Düşümü HATA): Kampanya içindeki varyant '{variant_to_deduct_from_campaign.name}' farklı bir işletmeye ait. Sipariş ID: {order.id}")
                                continue

                            quantity_to_deduct_for_this_item = campaign_bundle_quantity * campaign_item_instance.quantity
                            try:
                                stock_entry = Stock.objects.select_for_update().get(variant=variant_to_deduct_from_campaign)
                                original_quantity = stock_entry.quantity
                                
                                if original_quantity < quantity_to_deduct_for_this_item:
                                    logger.warning(
                                        f"SİNYAL (Kampanya Stok Uyarısı): Varyant '{variant_to_deduct_from_campaign.name}' için stok yetersiz. "
                                        f"İstenen: {quantity_to_deduct_for_this_item}, Mevcut: {original_quantity}. Stok 0 olarak ayarlanacak."
                                    )
                                    stock_entry.quantity = 0
                                else:
                                    stock_entry.quantity = F('quantity') - quantity_to_deduct_for_this_item
                                
                                stock_entry.save(update_fields=['quantity'])
                                stock_entry.refresh_from_db()

                                StockMovement.objects.create(
                                    stock=stock_entry, variant=variant_to_deduct_from_campaign, movement_type='SALE',
                                    quantity_change=-quantity_to_deduct_for_this_item, quantity_before=original_quantity,
                                    quantity_after=stock_entry.quantity,
                                    user=order.taken_by_staff if order.taken_by_staff else order.customer,
                                    description=f"Kampanya '{campaign.name}' (Sipariş #{order.id}, Kalem #{order_item.id}) ile satış.", related_order=order
                                )
                                logger.info(f"SİNYAL (Kampanya Stok Düşümü Başarılı): Varyant: {variant_to_deduct_from_campaign.name}, Düşülen: {quantity_to_deduct_for_this_item}, Yeni Stok: {stock_entry.quantity}")
                            except Stock.DoesNotExist:
                                logger.error(f"SİNYAL (Kampanya Stok Hatası): Varyant '{variant_to_deduct_from_campaign.name}' için stok kaydı bulunamadı. Sipariş ID: {order.id}")
                            except Exception as e_campaign_stock:
                                logger.error(f"SİNYAL (Kampanya Stok Düşümü Genel Hata): Varyant ID: {variant_to_deduct_from_campaign.id if variant_to_deduct_from_campaign else 'Bilinmiyor'}, Hata: {e_campaign_stock}", exc_info=True)
                        else:
                            logger.warning(f"SİNYAL (Kampanya Stok Düşümü UYARI): Kampanya '{campaign.name}' içindeki '{campaign_item_instance.menu_item.name}' ürünü için düşülecek varyant belirlenemedi.")
                else:
                    logger.error(f"SİNYAL (Stok Düşümü - Kampanya): Sipariş Kalemi ID {order_item.id} bir kampanya paketini temsil ediyor ama ilgili CampaignMenu bulunamadı veya işletme eşleşmiyor.")
            else: # Normal ürün veya varyant için stok düşümü
                variant_to_deduct = None
                if order_item.variant:
                    variant_to_deduct = order_item.variant
                    if variant_to_deduct.menu_item.business != order.business:
                        logger.error(f"SİNYAL (Stok Düşümü Hata): Varyant {variant_to_deduct.name} farklı bir işletmeye ait. Sipariş ID: {order.id}")
                        continue
                elif order_item.menu_item: 
                    non_extra_variants = order_item.menu_item.variants.filter(is_extra=False)
                    if non_extra_variants.count() == 1:
                        variant_to_deduct = non_extra_variants.first()
                    else:
                        logger.warning(f"SİNYAL (Stok Düşümü Uyarı/Hata): Ürün '{order_item.menu_item.name}' için variant belirtilmemiş ve uygun tekil normal varyant bulunamadı ({non_extra_variants.count()} adet). Stok düşümü atlanıyor olabilir.")
                        continue
                else: 
                    logger.error(f"SİNYAL (Stok Düşümü Hata): Sipariş Kalemi ID {order_item.id} için ürün veya varyant bilgisi eksik.")
                    continue
                
                if not variant_to_deduct:
                    logger.error(f"SİNYAL (Stok Düşümü HATA): Kalem ID {order_item.id} için stoktan düşülecek varyant belirlenemedi.")
                    continue

                try:
                    stock_entry = Stock.objects.select_for_update().get(variant=variant_to_deduct)
                    original_quantity = stock_entry.quantity
                    quantity_to_deduct_val = order_item.quantity
                    
                    if original_quantity < quantity_to_deduct_val:
                        logger.warning(
                            f"SİNYAL (Stok Uyarısı): Varyant '{variant_to_deduct.name}' (ID: {variant_to_deduct.id}) için stok yetersiz. "
                            f"İstenen: {quantity_to_deduct_val}, Mevcut: {original_quantity}. Stok 0 olarak ayarlanacak."
                        )
                        stock_entry.quantity = 0
                    else:
                        stock_entry.quantity = F('quantity') - quantity_to_deduct_val
                    
                    stock_entry.save(update_fields=['quantity'])
                    stock_entry.refresh_from_db()

                    StockMovement.objects.create(
                        stock=stock_entry, variant=variant_to_deduct, movement_type='SALE',
                        quantity_change=-quantity_to_deduct_val, quantity_before=original_quantity,
                        quantity_after=stock_entry.quantity,
                        user=order.taken_by_staff if order.taken_by_staff else order.customer,
                        description=f"Sipariş #{order.id} ile satış.", related_order=order
                    )
                    logger.info(f"SİNYAL (Stok Düşümü Başarılı): Varyant: {variant_to_deduct.name}, Düşülen Miktar: {quantity_to_deduct_val}, Yeni Stok: {stock_entry.quantity}")
                except Stock.DoesNotExist:
                    logger.error(f"SİNYAL (Stok Hatası): Varyant '{variant_to_deduct.name}' (ID: {variant_to_deduct.id}) için stok kaydı bulunamadı. Stok düşülemedi. Sipariş ID: {order.id}")
                except Exception as e:
                    logger.error(f"SİNYAL (Stok Düşümü Sırasında Genel Hata): Varyant ID: {variant_to_deduct.id if variant_to_deduct else 'Bilinmiyor'}, Hata: {e}", exc_info=True)
            
                if not order_item.menu_item.is_campaign_bundle:
                    for extra_item in order_item.extras.all().select_related('variant', 'variant__menu_item__business'):
                        extra_variant = extra_item.variant
                        if extra_variant.menu_item.business != order.business:
                            logger.error(f"SİNYAL (Ekstra Stok Düşümü HATA): Ekstra Varyant '{extra_variant.name}' farklı bir işletmeye ait. Sipariş ID: {order.id}")
                            continue
                        try:
                            extra_stock_entry = Stock.objects.select_for_update().get(variant=extra_variant)
                            original_quantity_extra = extra_stock_entry.quantity
                            quantity_to_deduct_extra = order_item.quantity * extra_item.quantity

                            if original_quantity_extra < quantity_to_deduct_extra:
                                logger.warning(f"SİNYAL (Ekstra Stok Uyarısı): Ekstra Varyant '{extra_variant.name}' için stok yetersiz. İstenen: {quantity_to_deduct_extra}, Mevcut: {original_quantity_extra}. Stok 0.")
                                extra_stock_entry.quantity = 0
                            else:
                                extra_stock_entry.quantity = F('quantity') - quantity_to_deduct_extra
                            
                            extra_stock_entry.save(update_fields=['quantity'])
                            extra_stock_entry.refresh_from_db()

                            StockMovement.objects.create(
                                stock=extra_stock_entry, variant=extra_variant, movement_type='SALE',
                                quantity_change=-quantity_to_deduct_extra, quantity_before=original_quantity_extra,
                                quantity_after=extra_stock_entry.quantity,
                                user=order.taken_by_staff if order.taken_by_staff else order.customer,
                                description=f"Sipariş #{order.id} için ekstra satışı ({order_item.menu_item.name} - {extra_variant.name}).",
                                related_order=order
                            )
                            logger.info(f"SİNYAL (Ekstra Stok Düşümü Başarılı): Ekstra Varyant: {extra_variant.name}, Düşülen Miktar: {quantity_to_deduct_extra}, Yeni Stok: {extra_stock_entry.quantity}")
                        except Stock.DoesNotExist:
                            logger.error(f"SİNYAL (Ekstra Stok Hatası): Ekstra Varyant '{extra_variant.name}' (ID: {extra_variant.id}) için stok kaydı bulunamadı. Sipariş ID: {order.id}")
                        except Exception as e_extra_stock:
                            logger.error(f"SİNYAL (Ekstra Stok Düşümü Sırasında Genel Hata): Ekstra Varyant ID: {extra_variant.id}, Hata: {e_extra_stock}", exc_info=True)
    else:
        logger.debug(
            f"SİNYAL (Stok Düşümü): Koşullar sağlanmadı. Payment ID: {instance.id}, created: {created}, "
            f"order: {'Mevcut' if instance.order else 'Yok'}, "
            f"order.is_paid: {instance.order.is_paid if instance.order else 'N/A'}"
        )