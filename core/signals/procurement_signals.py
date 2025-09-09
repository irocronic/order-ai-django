# core/signals/procurement_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction, models # models importu eklendi
from ..models import PurchaseOrder, IngredientStockMovement, Ingredient # Ingredient importu eklendi

@receiver(post_save, sender=PurchaseOrder)
def update_stock_on_purchase_order_completion(sender, instance, created, **kwargs):
    # Sadece "tamamlandı" durumuna geçildiğinde çalışmasını sağlamak için update_fields kontrolü
    update_fields = kwargs.get('update_fields')
    if not created and instance.status == 'completed' and update_fields and 'status' in update_fields:
        with transaction.atomic():
            for item in instance.items.select_related('ingredient').all():
                ingredient = item.ingredient
                original_quantity = ingredient.stock_quantity
                new_quantity = original_quantity + item.quantity
                
                update_fields_for_ingredient = ['stock_quantity']
                
                # +++++++++++++++ YENİ KONTROL: Bayrağı sıfırla +++++++++++++++
                # Eğer yeni stok miktarı uyarı eşiğinin üzerine çıktıysa,
                # bildirim bayrağını sıfırla ki bir sonraki düşüşte tekrar e-posta gidebilsin.
                if ingredient.alert_threshold is not None and new_quantity > ingredient.alert_threshold:
                    if ingredient.low_stock_notification_sent:
                        ingredient.low_stock_notification_sent = False
                        update_fields_for_ingredient.append('low_stock_notification_sent')
                        print(f"Stok eklendi. '{ingredient.name}' için düşük stok bildirim bayrağı sıfırlandı.")
                # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

                ingredient.stock_quantity = new_quantity
                ingredient.save(update_fields=update_fields_for_ingredient)

                IngredientStockMovement.objects.create(
                    ingredient=ingredient,
                    movement_type='ADDITION',
                    quantity_change=item.quantity,
                    quantity_before=original_quantity,
                    quantity_after=ingredient.stock_quantity,
                    description=f"Alım Faturası #{instance.id} ile stok girişi.",
                )