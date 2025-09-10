# core/signals/procurement_signals.py (Yeni dosya)
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from ..models import PurchaseOrder, IngredientStockMovement

@receiver(post_save, sender=PurchaseOrder)
def update_stock_on_purchase_order_completion(sender, instance, created, **kwargs):
    if not created and instance.status == 'completed' and instance.completed_at is not None:
        # İşlemin tekrar tekrar çalışmasını önlemek için bir kontrol mekanizması eklenebilir.
        # Örneğin, siparişin daha önce işlenip işlenmediğini kontrol eden bir flag.

        with transaction.atomic():
            for item in instance.items.select_related('ingredient').all():
                ingredient = item.ingredient
                original_quantity = ingredient.stock_quantity
                ingredient.stock_quantity += item.quantity
                ingredient.save()

                IngredientStockMovement.objects.create(
                    ingredient=ingredient,
                    movement_type='ADDITION', # Stok Girişi (Alım)
                    quantity_change=item.quantity,
                    quantity_before=original_quantity,
                    quantity_after=ingredient.stock_quantity,
                    description=f"Alım Siparişi #{instance.id} ile stok girişi.",
                    # user alanı, işlemi yapan kullanıcı olarak ayarlanabilir
                )