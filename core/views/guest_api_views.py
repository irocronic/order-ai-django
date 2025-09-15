# core/views/guest_api_views.py

from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.db import transaction, IntegrityError
from django.db.models import Q, Prefetch
from asgiref.sync import async_to_sync
import logging
from collections import Counter
from decimal import Decimal
from rest_framework.exceptions import ValidationError

# === DEĞİŞİKLİK BURADA: Artık sinyal yerine doğrudan Celery task'ini import ediyoruz ===
from ..tasks import send_order_update_task

from makarna_project.asgi import sio
from ..models import (
    Table, MenuItem, Order, OrderItem, OrderItemExtra, MenuItemVariant,
    Category, Business, CampaignMenu
)
from ..serializers import (
    GuestOrderCreateSerializer, MenuItemSerializer, CategorySerializer, OrderSerializer, GuestOrderItemSerializer
)

logger = logging.getLogger(__name__)

def add_item_to_guest_order(order: Order, item_data_dict: dict, is_awaiting_staff_approval_flag: bool):
    """
    Mevcut bir siparişe ürün ekler veya miktarını günceller.
    item_data_dict: GuestOrderItemSerializer.validate() tarafından döndürülen ve işlenmiş verileri içerir.
    is_awaiting_staff_approval_flag: Yeni veya güncellenen OrderItem için bu flag'in değeri.
    """
    menu_item_instance = item_data_dict.get('menu_item_instance')
    variant_instance = item_data_dict.get('variant_instance')
    quantity_to_add = item_data_dict.get('quantity', 1)
    table_user = item_data_dict.get('table_user', None)
    valid_extras_instances = item_data_dict.get('valid_extras_instances', [])

    if not menu_item_instance:
        logger.error("Hata: add_item_to_guest_order -> menu_item_instance bulunamadı.")
        raise ValidationError({"detail": "Sipariş kalemi için ürün bilgisi eksik."})

    incoming_extras_counter = Counter()
    if valid_extras_instances:
        for extra_detail in valid_extras_instances:
            if isinstance(extra_detail.get('variant_instance'), MenuItemVariant):
                incoming_extras_counter[(extra_detail['variant_instance'].id, extra_detail.get('quantity', 1))] += 1

    matching_items_query = order.order_items.filter(
        menu_item=menu_item_instance,
        variant=variant_instance,
        is_awaiting_staff_approval=is_awaiting_staff_approval_flag
    ).prefetch_related('extras__variant')

    found_item = None
    for existing_item in matching_items_query:
        existing_extras_counter = Counter(
            (extra.variant_id, extra.quantity) for extra in existing_item.extras.all()
        )
        if existing_extras_counter == incoming_extras_counter:
            found_item = existing_item
            break

    item_price_per_unit = Decimal('0.00')

    if menu_item_instance.is_campaign_bundle:
        try:
            campaign = menu_item_instance.represented_campaign
            if campaign and campaign.is_active:
                from django.utils import timezone # Fonksiyon içinde import
                now_date = timezone.now().date()
                if (campaign.start_date and campaign.start_date > now_date) or \
                   (campaign.end_date and campaign.end_date < now_date):
                    raise ValidationError(f"'{campaign.name}' kampanyası şu an geçerli değil.")
                item_price_per_unit = campaign.campaign_price
            else:
                raise ValidationError(f"Kampanya '{menu_item_instance.name}' aktif değil veya bulunamadı.")
        except (CampaignMenu.DoesNotExist, AttributeError):
            raise ValidationError(f"Kampanya '{menu_item_instance.name}' için kampanya detayı düzgün tanımlanmamış/bulunamadı.")
    else:
        main_price = variant_instance.price if variant_instance else Decimal('0.00')
        extras_total_price = sum(
            extra_detail['variant_instance'].price * Decimal(str(extra_detail.get('quantity', 1)))
            for extra_detail in valid_extras_instances if isinstance(extra_detail.get('variant_instance'), MenuItemVariant)
        )
        item_price_per_unit = main_price + extras_total_price

    with transaction.atomic():
        if found_item:
            found_item.quantity += quantity_to_add
            found_item.price = item_price_per_unit
            found_item.save(update_fields=['quantity', 'price'])
            processed_item = found_item
            logger.info(f"Guest Add: OrderItem ID {found_item.id} miktarı {quantity_to_add} artırıldı. Yeni miktar: {found_item.quantity}.")
        else:
            kds_status_for_new_item = OrderItem.KDS_ITEM_STATUS_CHOICES[0][0] if menu_item_instance.category and menu_item_instance.category.assigned_kds else None
            order_item = OrderItem.objects.create(
                order=order,
                menu_item=menu_item_instance,
                variant=variant_instance,
                quantity=quantity_to_add,
                table_user=None,
                price=item_price_per_unit,
                is_awaiting_staff_approval=is_awaiting_staff_approval_flag,
                kds_status=kds_status_for_new_item
            )
            for extra_data in valid_extras_instances:
                if isinstance(extra_data.get('variant_instance'), MenuItemVariant):
                    OrderItemExtra.objects.create(
                        order_item=order_item,
                        variant=extra_data['variant_instance'],
                        quantity=extra_data.get('quantity', 1)
                    )
            processed_item = order_item
            logger.info(f"Guest Add: Yeni OrderItem ID {order_item.id} Sipariş ID {order.id} için oluşturuldu.")

    return OrderItem.objects.select_related('menu_item', 'menu_item__category', 'variant').prefetch_related('extras__variant').get(id=processed_item.id)


class GuestOrderCreateView(generics.GenericAPIView):
    serializer_class = GuestOrderCreateSerializer
    permission_classes = [AllowAny]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        if hasattr(self, 'table_instance_for_context') and self.table_instance_for_context:
            context['business_from_context'] = self.table_instance_for_context.business
            context['table_uuid_from_url'] = str(self.table_instance_for_context.uuid)
        else:
            logger.warning("GuestOrderCreateView.get_serializer_context: table_instance_for_context set edilmemiş olabilir.")
        return context

    def post(self, request, table_uuid):
        try:
            self.table_instance_for_context = Table.objects.select_related('business').get(uuid=table_uuid)
        except Table.DoesNotExist:
            logger.warning(f"GuestOrderCreateView: Geçersiz masa UUID'si {table_uuid} için istek alındı.")
            return Response({'detail': 'Geçersiz masa kodu.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"GuestOrderCreateView validasyon hatası: {e.detail} - İstek Verisi: {request.data}", exc_info=False)
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        validated_data_from_serializer = serializer.validated_data
        table_instance = self.table_instance_for_context
        business_instance = table_instance.business
        items_to_add_data_list = validated_data_from_serializer.get('order_items_data', [])

        if not items_to_add_data_list:
            return Response({'order_items_data': ['Siparişe eklenecek ürün bulunmuyor.']}, status=status.HTTP_400_BAD_REQUEST)

        final_order_to_return = None
        response_status_code = status.HTTP_200_OK

        with transaction.atomic():
            active_order = Order.objects.filter(
                table=table_instance,
                business=business_instance,
                is_paid=False,
                credit_payment_details__isnull=True
            ).exclude(
                Q(status=Order.STATUS_COMPLETED) | Q(status=Order.STATUS_CANCELLED) | Q(status=Order.STATUS_REJECTED)
            ).order_by('-created_at').first()

            if active_order:
                logger.info(f"Masa {table_instance.table_number} için mevcut aktif sipariş (ID: {active_order.id}, Durum: {active_order.status}) bulundu. Ürünler bu siparişe eklenecek/güncellenecek.")
                from django.utils import timezone
                for item_data_dict in items_to_add_data_list:
                    add_item_to_guest_order(active_order, item_data_dict, is_awaiting_staff_approval_flag=True)

                if active_order.status != Order.STATUS_PENDING_APPROVAL or active_order.taken_by_staff is not None:
                    logger.info(f"Sipariş #{active_order.id} misafir tarafından güncellendi. Durum '{Order.STATUS_PENDING_APPROVAL}' olarak sıfırlanıyor.")
                    active_order.status = Order.STATUS_PENDING_APPROVAL
                    active_order.taken_by_staff = None
                    active_order.prepared_by_kitchen_staff = None
                    active_order.kitchen_completed_at = None
                    active_order.delivered_at = None
                    active_order.save(update_fields=['status', 'taken_by_staff', 'prepared_by_kitchen_staff', 'kitchen_completed_at', 'delivered_at'])
                else:
                    active_order.save()

                final_order_to_return = active_order
                response_status_code = status.HTTP_200_OK
            else:
                logger.info(f"Masa {table_instance.table_number} için yeni misafir siparişi oluşturuluyor.")
                final_order_to_return = serializer.save(
                    business=business_instance,
                    table=table_instance,
                    customer=None,
                    taken_by_staff=None,
                    status=Order.STATUS_PENDING_APPROVAL
                )
                if final_order_to_return:
                    final_order_to_return.order_items.update(is_awaiting_staff_approval=True)
                    logger.info(f"Yeni misafir siparişi #{final_order_to_return.id} oluşturuldu ve tüm kalemler onaya ayarlandı.")
                response_status_code = status.HTTP_201_CREATED

        if final_order_to_return:
            # === DEĞİŞİKLİK BURADA: Celery task'i doğrudan çağrılıyor ===
            is_newly_created = response_status_code == status.HTTP_201_CREATED
            event_type = 'guest_order_pending_approval'
            message = f"Masa {table_instance.table_number} için yeni misafir siparişi onay bekliyor." if is_newly_created else f"Masa {table_instance.table_number} siparişine ürün eklendi, onay bekliyor."
            transaction.on_commit(
                lambda: send_order_update_task.delay(
                    order_id=final_order_to_return.id,
                    event_type=event_type,
                    message=message
                )
            )
            final_order_to_return.refresh_from_db()
            full_order_serializer = OrderSerializer(final_order_to_return, context=self.get_serializer_context())
            return Response(full_order_serializer.data, status=response_status_code)
        else:
            logger.error("GuestOrderCreateView: Sipariş oluşturma/güncelleme sonrası final_order_to_return None kaldı.")
            return Response({"detail": "Sipariş işlenirken beklenmedik bir sorun oluştu."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GuestMenuView(generics.ListAPIView):
    serializer_class = MenuItemSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return MenuItem.objects.none()

    def get_serializer_context(self):
        return {'request': self.request}

    def get(self, request, table_uuid):
        try:
            table = get_object_or_404(Table.objects.select_related('business'), uuid=table_uuid)
            business = table.business
        except (ValueError, Table.DoesNotExist, Http404):
            return Response({"detail": "Geçersiz veya bulunamayan masa kodu."}, status=status.HTTP_404_NOT_FOUND)

        active_order = Order.objects.filter(
            table=table,
            business=business,
            customer__isnull=True,
            is_paid=False,
            credit_payment_details__isnull=True
        ).exclude(
            Q(status=Order.STATUS_REJECTED) | Q(status=Order.STATUS_CANCELLED) | Q(status=Order.STATUS_COMPLETED)
        ).prefetch_related(
            Prefetch('order_items', queryset=OrderItem.objects.select_related('menu_item__category', 'variant').prefetch_related('extras__variant')),
            'table_users'
        ).select_related('payment_info', 'taken_by_staff').order_by('-created_at').first()

        active_order_data = None
        if active_order:
            active_order_data = OrderSerializer(active_order, context=self.get_serializer_context()).data

        menu_items_qs = MenuItem.objects.filter(business=business, is_active=True).prefetch_related(
            'variants'
        ).select_related('category', 'category__parent')

        categories_qs = Category.objects.filter(business=business).prefetch_related('subcategories')

        menu_item_serializer = MenuItemSerializer(menu_items_qs, many=True, context=self.get_serializer_context())
        category_serializer = CategorySerializer(categories_qs, many=True, context=self.get_serializer_context())

        return Response({
            'menu_items': menu_item_serializer.data,
            'categories': category_serializer.data,
            'business_name': business.name,
            'table_number': table.table_number,
            'table_uuid': str(table.uuid),
            'active_order': active_order_data,
        }, status=status.HTTP_200_OK)


class GuestTakeawayMenuView(generics.ListAPIView):
    serializer_class = MenuItemSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return MenuItem.objects.none()

    def get(self, request, order_uuid):
        try:
            active_order = Order.objects.filter(
                uuid=order_uuid,
                order_type='takeaway'
            ).exclude(
                Q(status__in=[Order.STATUS_COMPLETED, Order.STATUS_CANCELLED, Order.STATUS_REJECTED])
            ).prefetch_related(
                Prefetch('order_items', queryset=OrderItem.objects.select_related('menu_item__category', 'variant').prefetch_related('extras__variant'))
            ).select_related('business').first()

            if not active_order:
                return Response({"detail": "Geçersiz veya tamamlanmış sipariş linki."}, status=status.HTTP_404_NOT_FOUND)

            business = active_order.business
            menu_items_qs = MenuItem.objects.filter(business=business, is_active=True).prefetch_related('variants__stock').select_related('category', 'category__parent')
            categories_qs = Category.objects.filter(business=business).prefetch_related('subcategories')

            menu_item_serializer = MenuItemSerializer(menu_items_qs, many=True, context={'request': request})
            category_serializer = CategorySerializer(categories_qs, many=True, context={'request': request})
            active_order_data = OrderSerializer(active_order, context={'request': request}).data

            return Response({
                'menu_items': menu_item_serializer.data,
                'categories': category_serializer.data,
                'business_name': business.name,
                'active_order': active_order_data,
            }, status=status.HTTP_200_OK)

        except (ValueError, Order.DoesNotExist, Http404):
            return Response({"detail": "Geçersiz sipariş kodu."}, status=status.HTTP_404_NOT_FOUND)


class GuestTakeawayOrderUpdateView(generics.GenericAPIView):
    serializer_class = GuestOrderItemSerializer
    permission_classes = [AllowAny]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        if hasattr(self, 'business_instance_for_context'):
            context['business_from_context'] = self.business_instance_for_context
        return context

    def post(self, request, order_uuid):
        try:
            order_to_update = Order.objects.filter(
                uuid=order_uuid,
                order_type='takeaway'
            ).exclude(
                Q(status__in=[Order.STATUS_COMPLETED, Order.STATUS_CANCELLED, Order.STATUS_REJECTED])
            ).first()

            if not order_to_update:
                return Response({"detail": "Sipariş bulunamadı veya güncellenemez durumda."}, status=status.HTTP_404_NOT_FOUND)
            
            self.business_instance_for_context = order_to_update.business

            serializer = self.get_serializer(data=request.data, many=True)
            serializer.is_valid(raise_exception=True)
            validated_items = serializer.validated_data

            if not validated_items:
                return Response({'detail': 'Eklenecek ürün bulunmuyor.'}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                for item_data_dict in validated_items:
                    add_item_to_guest_order(order_to_update, item_data_dict, is_awaiting_staff_approval_flag=True)

                order_to_update.status = Order.STATUS_PENDING_APPROVAL
                order_to_update.save(update_fields=['status'])

            # === DEĞİŞİKLİK BURADA: Celery task'i doğrudan çağrılıyor ===
            event_type = 'existing_order_needs_reapproval'
            message = f"Paket sipariş #{order_to_update.id} güncellendi ve yeniden onay bekliyor."
            transaction.on_commit(
                lambda: send_order_update_task.delay(
                    order_id=order_to_update.id,
                    event_type=event_type,
                    message=message
                )
            )

            order_to_update.refresh_from_db()
            final_order_data = OrderSerializer(order_to_update, context={'request': request}).data

            return Response(final_order_data, status=status.HTTP_200_OK)

        except (ValueError, Order.DoesNotExist):
            return Response({"detail": "Geçersiz sipariş kodu."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            logger.warning(f"GuestTakeawayOrderUpdateView validasyon hatası: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)