# core/serializers/order_serializers.py

from rest_framework import serializers, generics
from django.db import transaction
from django.db.models import Prefetch, Q
from decimal import Decimal
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
import logging

from ..models import (
    Order, OrderItem, OrderItemExtra, MenuItem, MenuItemVariant, Table,
    CustomUser as User, OrderTableUser, Business, Pager,
    CampaignMenu, CampaignMenuItem, KDSScreen
)
from .menu_serializers import MenuItemSerializer, MenuItemVariantSerializer
from .payment_serializers import PaymentSerializer, CreditPaymentDetailsSerializer
from .pager_serializers import PagerSerializer as FullPagerInfoSerializer
# === DEĞİŞİKLİK BURADA: Import yolunu yeni util dosyasından alıyoruz ===
from ..utils.json_helpers import convert_decimals_to_strings

logger = logging.getLogger(__name__)

# Yerel fonksiyon tanımı kaldırıldı.

class SimplePagerInfoSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    class Meta:
        model = Pager
        fields = ['id', 'device_id', 'name', 'status', 'status_display']

class OrderItemExtraSerializer(serializers.ModelSerializer):
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    variant_price = serializers.DecimalField(source='variant.price', max_digits=8, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItemExtra
        fields = ['id', 'variant', 'quantity', 'variant_name', 'variant_price']


class GuestOrderItemSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField(write_only=True)
    variant_id = serializers.IntegerField(required=False, allow_null=True, write_only=True, source='variant')
    quantity = serializers.IntegerField(default=1, min_value=1)
    table_user = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    extras = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True
    )

    def validate(self, data):
        menu_item_id = data.get('menu_item_id')
        if menu_item_id is None:
            raise ValidationError({"menu_item_id": "menu_item_id gereklidir."})

        business_from_context = self.context.get('business_from_context')
        if not business_from_context:
            logger.error("GuestOrderItemSerializer: business_from_context eksik.")
            raise ValidationError("İşlem yapılacak işletme belirlenemedi (serializer context hatası).")

        try:
            menu_item = MenuItem.objects.select_related('business', 'represented_campaign__business').get(id=menu_item_id, business=business_from_context)
            data['menu_item_instance'] = menu_item
        except MenuItem.DoesNotExist:
            raise ValidationError(f"ID'si {menu_item_id} olan ürün bu işletmede bulunamadı veya geçersiz.")

        if not menu_item.is_campaign_bundle:
            variant_obj = data.get('variant')
            if variant_obj:
                try:
                    variant_instance = MenuItemVariant.objects.get(id=variant_obj, menu_item=menu_item)
                    if variant_instance.is_extra:
                        raise ValidationError({"variant_id": "Seçilen varyant bir ana seçenek olmalı, ekstra değil."})
                    data['variant_instance'] = variant_instance
                except MenuItemVariant.DoesNotExist:
                    raise ValidationError(f"ID'si {variant_obj} olan varyant, ürün ID {menu_item_id} için bulunamadı.")
            else:
                if menu_item.variants.filter(is_extra=False).exists():
                    raise ValidationError(f"'{menu_item.name}' ürünü için lütfen bir seçenek (varyant) belirtin.")
                data['variant_instance'] = None

            extras_data = data.get('extras', [])
            valid_extras = []
            for extra_item_data in extras_data:
                extra_variant_id_raw = extra_item_data.get('variant')
                extra_quantity = extra_item_data.get('quantity', 1)

                if extra_variant_id_raw is None: continue
                try:
                    extra_variant_id = int(extra_variant_id_raw)
                    if not isinstance(extra_quantity, int) or extra_quantity < 1: extra_quantity = 1

                    extra_variant = MenuItemVariant.objects.get(
                        id=extra_variant_id,
                        is_extra=True
                    )
                    valid_extras.append({
                        'variant_instance': extra_variant,
                        'quantity': extra_quantity
                    })
                except (ValueError, TypeError, MenuItemVariant.DoesNotExist):
                    logger.warning(f"Geçersiz ekstra (ID: {extra_variant_id_raw}) ürün ID {menu_item_id} için gönderildi.")
                    pass
            data['valid_extras_instances'] = valid_extras
        else:
            data['variant_instance'] = None
            data['valid_extras_instances'] = []
        return data


class OrderItemSerializer(serializers.ModelSerializer):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all(), required=False)
    menu_item = MenuItemSerializer(read_only=True)
    variant = MenuItemVariantSerializer(read_only=True)
    extras = OrderItemExtraSerializer(many=True, read_only=True)
    table_user = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    delivered = serializers.BooleanField(read_only=True)
    is_awaiting_staff_approval = serializers.BooleanField(read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    kds_status = serializers.CharField(read_only=True, allow_null=True)
    kds_status_display = serializers.CharField(source='get_kds_status_display', read_only=True, allow_null=True)
    item_prepared_by_staff_username = serializers.CharField(source='item_prepared_by_staff.username', read_only=True, allow_null=True)
    
    waiter_picked_up_at = serializers.DateTimeField(read_only=True, allow_null=True)

    menu_item_id = serializers.PrimaryKeyRelatedField(
        queryset=MenuItem.objects.all(), source='menu_item', write_only=True, required=False
    )
    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=MenuItemVariant.objects.all(), source='variant', write_only=True, required=False, allow_null=True
    )
    
    kdv_rate = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    kdv_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'menu_item', 'menu_item_id', 'variant', 'variant_id',
            'quantity', 'price', 'extras', 'table_user', 'delivered',
            'is_awaiting_staff_approval',
            'kds_status', 'kds_status_display', 'item_prepared_by_staff', 'item_prepared_by_staff_username',
            'waiter_picked_up_at', 'kdv_rate', 'kdv_amount'
        ]
        read_only_fields = [
            'order', 'menu_item', 'variant', 'extras', 'price', 'delivered',
            'is_awaiting_staff_approval', 'kds_status', 'kds_status_display',
            'item_prepared_by_staff', 'item_prepared_by_staff_username',
            'waiter_picked_up_at', 'kdv_rate', 'kdv_amount'
        ]

class OrderTableUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTableUser
        fields = ['id', 'name']


class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)
    order_items_data = GuestOrderItemSerializer(many=True, write_only=True, required=False)
    payment = PaymentSerializer(source='payment_info', read_only=True)
    credit_details = CreditPaymentDetailsSerializer(source='credit_payment_details', read_only=True)

    approved_at = serializers.DateTimeField(read_only=True)
    kitchen_completed_at = serializers.DateTimeField(read_only=True)
    picked_up_by_waiter_at = serializers.DateTimeField(read_only=True)
    delivered_at = serializers.DateTimeField(read_only=True)

    is_split_table = serializers.BooleanField(required=False, default=False)
    table_users = OrderTableUserSerializer(many=True, read_only=True)
    table_users_data = serializers.ListField(
        child=serializers.CharField(max_length=100),
        write_only=True,
        required=False,
        allow_empty=True
    )
    table = serializers.PrimaryKeyRelatedField(queryset=Table.objects.all(), required=False, allow_null=True)
    customer = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(user_type='customer'), required=False, allow_null=True)

    taken_by_staff_username = serializers.CharField(source='taken_by_staff.username', read_only=True, allow_null=True)
    prepared_by_kitchen_staff_username = serializers.CharField(source='prepared_by_kitchen_staff.username', read_only=True, allow_null=True)

    status = serializers.ChoiceField(choices=Order.ORDER_STATUS_CHOICES, required=False)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    business = serializers.PrimaryKeyRelatedField(queryset=Business.objects.all(), required=False)

    assigned_pager_info = SimplePagerInfoSerializer(source='assigned_pager_instance', read_only=True, allow_null=True)
    pager_device_id_to_assign = serializers.CharField(
        write_only=True,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Bu siparişe atanacak çağrı cihazının Bluetooth kimliği (örn: MAC adresi)."
    )
    uuid = serializers.UUIDField(read_only=True, format='hex_verbose')

    total_kdv_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    grand_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)


    class Meta:
        model = Order
        fields = [
            'id', 'uuid', 'customer', 'business', 'table', 'order_type', 'customer_name',
            'customer_phone', 'created_at', 
            'approved_at',
            'kitchen_completed_at',
            'picked_up_by_waiter_at',
            'delivered_at', 
            'is_paid', 'is_split_table', 'order_items', 'order_items_data',
            'table_users', 'table_users_data', 'payment', 'credit_details',
            'taken_by_staff', 'taken_by_staff_username', 
            'prepared_by_kitchen_staff', 'prepared_by_kitchen_staff_username',
            'status', 'status_display', 
            'total_kdv_amount', 'grand_total',
            'assigned_pager_info',
            'pager_device_id_to_assign',
        ]
        read_only_fields = [
            'uuid', 'created_at', 'approved_at', 'kitchen_completed_at', 'picked_up_by_waiter_at', 'delivered_at',
            'status_display', 'taken_by_staff_username', 'prepared_by_kitchen_staff_username',
            'order_items', 'table_users', 'payment', 'credit_details',
            'total_kdv_amount', 'grand_total',
            'assigned_pager_info',
        ]

    def validate_table_users_data(self, value):
        is_split = self.initial_data.get('is_split_table', getattr(self.instance, 'is_split_table', False))
        if is_split and (not value or len(value) < 2):
            raise ValidationError("Bölünmüş masa için en az 2 masa sahibi adı gereklidir.")
        if value and any(not isinstance(name, str) or not name.strip() for name in value):
                raise ValidationError("Masa sahibi isimleri geçerli metinler olmalıdır.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        order_items_data_list = validated_data.pop('order_items_data', [])
        table_users_name_list = validated_data.pop('table_users_data', [])
        pager_ble_device_id_to_assign_on_create = validated_data.pop('pager_device_id_to_assign', None)

        request_user = self.context['request'].user
        is_staff_or_owner_creating = False
        if request_user and request_user.is_authenticated:
            if hasattr(request_user, 'user_type') and request_user.user_type in ['staff', 'business_owner', 'admin', 'kitchen_staff']:
                is_staff_or_owner_creating = True
        
        is_awaiting_approval_flag_for_items = not is_staff_or_owner_creating

        if 'status' not in validated_data:
            validated_data['status'] = Order.STATUS_PENDING_APPROVAL if not is_staff_or_owner_creating else Order.STATUS_APPROVED

        if not is_staff_or_owner_creating and 'taken_by_staff' in validated_data:
            validated_data.pop('taken_by_staff')
        elif is_staff_or_owner_creating and 'taken_by_staff' not in validated_data and hasattr(request_user, 'is_authenticated') and request_user.is_authenticated :
                validated_data['taken_by_staff'] = request_user

        if 'business' not in validated_data:
            business_from_context = self.context.get('business_from_context')
            if business_from_context:
                validated_data['business'] = business_from_context
            else:
                raise ValidationError({"business": "Sipariş için işletme bilgisi bulunamadı."})
        
        current_business_for_order = validated_data['business']

        order = Order.objects.create(**validated_data)

        default_kds_status_for_new_item = OrderItem.KDS_ITEM_STATUS_PENDING

        total_price_before_kdv = Decimal('0.00')
        total_kdv_amount = Decimal('0.00')

        for item_data_dict in order_items_data_list:
            menu_item_instance = item_data_dict.get('menu_item_instance')
            variant_instance = item_data_dict.get('variant_instance')
            quantity = item_data_dict.get('quantity', 1)
            table_user_name_from_item_data = item_data_dict.get('table_user')
            valid_extras_instances_data = item_data_dict.get('valid_extras_instances', [])

            if not menu_item_instance:
                logger.error(f"Order {order.id}: menu_item_instance missing in item_data_dict during OrderSerializer.create.")
                raise ValidationError({"order_items_data": "Her sipariş kalemi için geçerli bir ürün (menu_item_instance) sağlanmalıdır."})

            item_price_per_unit_before_kdv = Decimal('0.00')
            kdv_rate = menu_item_instance.kdv_rate

            if menu_item_instance.is_campaign_bundle:
                try:
                    campaign = menu_item_instance.represented_campaign
                    if campaign and campaign.is_active:
                        now_date = timezone.now().date()
                        if (campaign.start_date and campaign.start_date > now_date) or \
                           (campaign.end_date and campaign.end_date < now_date):
                            raise ValidationError(f"'{campaign.name}' kampanyası şu an geçerli değil.")
                        item_price_per_unit_before_kdv = campaign.campaign_price
                    else:
                        raise ValidationError(f"Kampanya '{menu_item_instance.name}' aktif değil veya bulunamadı.")
                except (CampaignMenu.DoesNotExist, AttributeError):
                    raise ValidationError(f"Kampanya '{menu_item_instance.name}' için kampanya detayı düzgün tanımlanmamış/bulunamadı.")
            else:
                main_price = variant_instance.price if variant_instance else Decimal('0.00')
                extras_total_price = sum(
                    extra_detail['variant_instance'].price * Decimal(str(extra_detail.get('quantity', 1)))
                    for extra_detail in valid_extras_instances_data if isinstance(extra_detail.get('variant_instance'), MenuItemVariant)
                )
                item_price_per_unit_before_kdv = main_price + extras_total_price
            
            line_total_before_kdv = item_price_per_unit_before_kdv * quantity
            total_price_before_kdv += line_total_before_kdv

            line_kdv_amount = line_total_before_kdv * (kdv_rate / Decimal('100'))
            total_kdv_amount += line_kdv_amount

            kds_status_for_this_item = None
            if menu_item_instance.category and menu_item_instance.category.assigned_kds:
                kds_status_for_this_item = default_kds_status_for_new_item

            order_item = OrderItem.objects.create(
                order=order,
                menu_item=menu_item_instance,
                variant=variant_instance, 
                quantity=quantity,
                table_user=table_user_name_from_item_data,
                price=item_price_per_unit_before_kdv,
                is_awaiting_staff_approval= is_awaiting_approval_flag_for_items,
                kds_status=kds_status_for_this_item,
                kdv_rate=kdv_rate,
                kdv_amount=line_kdv_amount
            )

            if not menu_item_instance.is_campaign_bundle:
                for extra_detail in valid_extras_instances_data:
                    if isinstance(extra_detail.get('variant_instance'), MenuItemVariant):
                        OrderItemExtra.objects.create(
                            order_item=order_item,
                            variant=extra_detail['variant_instance'],
                            quantity=extra_detail.get('quantity', 1)
                        )
        
        order.total_kdv_amount = total_kdv_amount
        order.grand_total = total_price_before_kdv + total_kdv_amount
        order.save(update_fields=['total_kdv_amount', 'grand_total'])
        
        if validated_data.get('is_split_table'):
            for user_name in table_users_name_list:
                if user_name.strip():
                    OrderTableUser.objects.create(order=order, name=user_name.strip())
        
        if pager_ble_device_id_to_assign_on_create:
            try:
                pager_to_assign = Pager.objects.get(device_id=pager_ble_device_id_to_assign_on_create, business=current_business_for_order)
                if pager_to_assign.status == 'available':
                    pager_to_assign.current_order = order
                    pager_to_assign.status = 'in_use'
                    pager_to_assign.save(update_fields=['current_order', 'status'])
                    logger.info(f"Order Create: Pager ID {pager_to_assign.id} yeni sipariş #{order.id}'e atandı.")
                else:
                    logger.warning(f"Order Create: Pager ID {pager_to_assign.id} ({pager_to_assign.device_id}) boşta değil, siparişe atanamadı.")
            except Pager.DoesNotExist:
                logger.warning(f"Order Create: Cihaz ID '{pager_ble_device_id_to_assign_on_create}' ile eşleşen Pager bulunamadı.")
            except Exception as e_pager:
                logger.error(f"Order Create: Pager atama sırasında hata: {e_pager}")
        return order

    @transaction.atomic
    def update(self, instance: Order, validated_data):
        validated_data.pop('order_items_data', None) 
        validated_data.pop('table_users_data', None)

        pager_ble_device_id_action = validated_data.pop('pager_device_id_to_assign', False)

        if pager_ble_device_id_action is not False:
            pager_to_assign_obj = None
            if pager_ble_device_id_action is not None and pager_ble_device_id_action.strip() != "":
                try:
                    pager_to_assign_obj = Pager.objects.get(device_id=pager_ble_device_id_action, business=instance.business)
                except Pager.DoesNotExist:
                    raise ValidationError({"pager_device_id_to_assign": f"Cihaz ID '{pager_ble_device_id_action}' ile eşleşen çağrı cihazı bulunamadı veya bu işletmeye ait değil."})
            
            current_assigned_pager = getattr(instance, 'assigned_pager_instance', None)
            if current_assigned_pager != pager_to_assign_obj:
                if current_assigned_pager:
                    current_assigned_pager.current_order = None
                    current_assigned_pager.status = 'available'
                    current_assigned_pager.save(update_fields=['current_order', 'status'])
                    logger.info(f"Order #{instance.id} için eski Pager #{current_assigned_pager.id} serbest bırakıldı.")
                
                if pager_to_assign_obj:
                    if pager_to_assign_obj.status != 'available':
                        if pager_to_assign_obj.current_order and pager_to_assign_obj.current_order != instance :
                            raise ValidationError(f"Çağrı cihazı '{pager_to_assign_obj}' zaten başka bir siparişe (#{pager_to_assign_obj.current_order_id}) atanmış.")
                        elif pager_to_assign_obj.status != 'in_use' or pager_to_assign_obj.current_order != instance :
                            raise ValidationError(f"Çağrı cihazı '{pager_to_assign_obj}' şu an kullanılamaz (Durum: {pager_to_assign_obj.get_status_display()}).")
                    
                    pager_to_assign_obj.current_order = instance
                    pager_to_assign_obj.status = 'in_use'
                    pager_to_assign_obj.save(update_fields=['current_order', 'status'])
                    logger.info(f"Order #{instance.id} için yeni Pager #{pager_to_assign_obj.id} atandı.")
                else:
                    logger.info(f"Order #{instance.id} üzerinden çağrı cihazı kaldırıldı.")
        
        order = super().update(instance, validated_data)
        return order


class GuestOrderCreateSerializer(OrderSerializer):
    class Meta(OrderSerializer.Meta):
        read_only_fields = OrderSerializer.Meta.read_only_fields + [
            'business', 
            'taken_by_staff', 
            'prepared_by_kitchen_staff',
        ]
        extra_kwargs = {
            'pager_device_id_to_assign': {'read_only': True, 'required': False}
        }

    def validate(self, data):
        if self.context.get('view') and isinstance(self.context['view'], generics.GenericAPIView):
            table_uuid_from_url = self.context['view'].kwargs.get('table_uuid')
            order_uuid_from_url = self.context['view'].kwargs.get('order_uuid')
            
            if table_uuid_from_url:
                try:
                    table_instance = Table.objects.get(uuid=table_uuid_from_url)
                    data['table'] = table_instance
                    if 'business' not in data and 'business_from_context' in self.context:
                        data['business'] = self.context['business_from_context']
                    elif 'business' not in data:
                        data['business'] = table_instance.business
                except Table.DoesNotExist:
                    raise ValidationError({"table_uuid": "Geçersiz masa kimliği."})
            elif not order_uuid_from_url:
                raise ValidationError({"detail": "Masa veya paket sipariş kimliği URL'de belirtilmelidir."})
        
        data['status'] = Order.STATUS_PENDING_APPROVAL
        data['customer'] = None 
        data['taken_by_staff'] = None
        return super().validate(data)


class KDSOrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True, allow_null=True)
    extras_display = serializers.SerializerMethodField(read_only=True)
    kds_status_display = serializers.CharField(source='get_kds_status_display', read_only=True, allow_null=True)
    item_prepared_by_staff_username = serializers.CharField(source='item_prepared_by_staff.username', read_only=True, allow_null=True)

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'menu_item_name',
            'variant_name',
            'quantity',
            'extras_display',
            'table_user',
            'delivered',
            'is_awaiting_staff_approval',
            'kds_status',
            'kds_status_display',
            'item_prepared_by_staff_username',
        ]

    def get_extras_display(self, obj: OrderItem):
        if obj.menu_item.is_campaign_bundle:
            return ""
        extras_qs = obj.extras.select_related('variant').all()
        if not extras_qs:
            return ""
        return ", ".join([f"{extra.variant.name} (x{extra.quantity})" for extra in extras_qs])


class KDSOrderSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    order_items = serializers.SerializerMethodField(method_name='get_filtered_kds_order_items')
    table_number = serializers.CharField(source='table.table_number', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    kds_screen_specific_status_display = serializers.SerializerMethodField()
    elapsed_time_since_creation_minutes = serializers.SerializerMethodField()
    taken_by_staff_username = serializers.CharField(source='taken_by_staff.username', read_only=True, allow_null=True)
    prepared_by_kitchen_staff_username = serializers.CharField(source='prepared_by_kitchen_staff.username', read_only=True, allow_null=True)

    assigned_pager_device_id = serializers.CharField(source='assigned_pager_instance.device_id', read_only=True, allow_null=True)
    assigned_pager_name = serializers.CharField(source='assigned_pager_instance.name', read_only=True, allow_null=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'display_name',
            'order_type',
            'table_number',
            'customer_name',
            'created_at',
            'status',
            'status_display',
            'kds_screen_specific_status_display',
            'order_items',
            'elapsed_time_since_creation_minutes',
            'taken_by_staff_username',
            'prepared_by_kitchen_staff_username',
            'kitchen_completed_at',
            'delivered_at',
            'assigned_pager_device_id',
            'assigned_pager_name',
        ]

    def get_display_name(self, obj: Order) -> str:
        if obj.order_type == 'table' and obj.table:
            return f"Masa {obj.table.table_number}"
        elif obj.customer_name:
            return obj.customer_name
        elif obj.customer:
            return obj.customer.username
        return f"Sipariş #{obj.id}"

    def get_elapsed_time_since_creation_minutes(self, obj: Order) -> int:
        if obj.kitchen_completed_at:
            return int((obj.kitchen_completed_at - obj.created_at).total_seconds() / 60)
        
        if obj.status in [Order.STATUS_COMPLETED, Order.STATUS_CANCELLED, Order.STATUS_REJECTED]:
            return 0 
        
        return int((timezone.now() - obj.created_at).total_seconds() / 60)

    def get_filtered_kds_order_items(self, obj: Order):
        target_kds_screen = self.context.get('target_kds_screen')
        
        if not target_kds_screen:
            logger.warning(f"KDSOrderSerializer: Order {obj.id} için target_kds_screen context'te bulunamadı.")
            relevant_items = obj.order_items.exclude(
                kds_status__in=[
                    OrderItem.KDS_ITEM_STATUS_READY,
                    OrderItem.KDS_ITEM_STATUS_PICKED_UP
                ]
            )
            return KDSOrderItemSerializer(relevant_items, many=True, context=self.context).data

        relevant_items_qs = obj.order_items.filter(
            Q(menu_item__category__assigned_kds_id=target_kds_screen.id) &
            Q(is_awaiting_staff_approval=False)
        ).exclude(
            kds_status__in=[
                OrderItem.KDS_ITEM_STATUS_READY,
                OrderItem.KDS_ITEM_STATUS_PICKED_UP
            ]
        ).select_related(
            'menu_item__category',
            'menu_item__represented_campaign',
            'item_prepared_by_staff',
            'variant'
        ).prefetch_related(
            'extras__variant'
        )
        
        logger.debug(f"KDSOrderSerializer: Order {obj.id}, KDS '{target_kds_screen.name}': Filtrelenmiş kalem sayısı {relevant_items_qs.count()}.")
        return KDSOrderItemSerializer(relevant_items_qs, many=True, context=self.context).data

    def get_kds_screen_specific_status_display(self, obj: Order) -> str:
        target_kds_screen = self.context.get('target_kds_screen')
        if not target_kds_screen:
            return obj.get_status_display()

        items_for_this_kds = obj.order_items.filter(
            menu_item__category__assigned_kds_id=target_kds_screen.id,
            is_awaiting_staff_approval=False,
            delivered=False
        )

        if not items_for_this_kds.exists():
            all_assigned_items_for_this_kds = obj.order_items.filter(
                menu_item__category__assigned_kds_id=target_kds_screen.id,
            )
            if all_assigned_items_for_this_kds.exists() and \
               not all_assigned_items_for_this_kds.exclude(kds_status=OrderItem.KDS_ITEM_STATUS_READY).exists():
                return f"{target_kds_screen.name}: Tamamlandı"
            
            return f"{target_kds_screen.name}: Bekleyen Ürün Yok"

        if items_for_this_kds.filter(kds_status=OrderItem.KDS_ITEM_STATUS_PREPARING).exists(): 
            return f"{target_kds_screen.name}: Hazırlanıyor"
        
        if items_for_this_kds.filter(kds_status=OrderItem.KDS_ITEM_STATUS_PENDING).exists(): 
            if obj.status == Order.STATUS_APPROVED:
                return f"{target_kds_screen.name}: Mutfağa İletildi"
            elif obj.status == Order.STATUS_PREPARING:
                return f"{target_kds_screen.name}: Beklemede"
            return f"{target_kds_screen.name}: Beklemede" 

        logger.warning(f"KDSOrderSerializer: Order {obj.id} için kds_screen_specific_status_display mantığında beklenmedik durum. KDS: {target_kds_screen.name}. Genel durum kullanılıyor.")
        return obj.get_status_display()