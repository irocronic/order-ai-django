# core/views/order_views.py

from django.db import transaction, connection
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import Q, Prefetch
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
import logging
from decimal import Decimal
from contextlib import contextmanager
from django.conf import settings

from rest_framework.pagination import PageNumberPagination

from ..models import (
    Order, OrderItem, OrderItemExtra, MenuItem, MenuItemVariant, Table,
    CreditPaymentDetails, Payment, Business, CustomUser as User, Pager
)
from ..serializers import OrderSerializer, OrderItemSerializer
from ..utils.order_helpers import PermissionKeys, get_user_business
from ..utils.json_helpers import convert_decimals_to_strings
from ..permissions import IsOnActiveShift
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from ..signals.order_signals import send_order_update_notification

from .order_actions import item_actions, status_actions, financial_actions, operational_actions

logger = logging.getLogger(__name__)

@contextmanager
def handle_db_lock_timeout(max_wait_time=5):
    """Database lock timeout'u yöneten context manager - DB engine'e uygun"""
    old_timeout = None
    try:
        # Database engine'ini tespit et
        engine = settings.DATABASES['default']['ENGINE']
        
        if 'postgresql' in engine.lower():
            # PostgreSQL için lock_timeout
            with connection.cursor() as cursor:
                # Mevcut değeri al
                cursor.execute("SHOW lock_timeout")
                old_timeout = cursor.fetchone()[0]
                # Yeni değeri set et (milisaniye cinsinden)
                cursor.execute(f"SET lock_timeout = '{max_wait_time * 1000}ms'")
                
        elif 'mysql' in engine.lower():
            # MySQL için innodb_lock_wait_timeout
            with connection.cursor() as cursor:
                cursor.execute("SELECT @@innodb_lock_wait_timeout")
                old_timeout = cursor.fetchone()[0]
                cursor.execute(f"SET innodb_lock_wait_timeout = {max_wait_time}")
                
        # SQLite için özel bir timeout ayarı yok, sadece geç
        
        yield
        
    except Exception as e:
        logger.error(f"Database lock timeout ayarı hatası: {e}")
        # Hata olursa da devam et, kritik değil
        yield
    finally:
        try:
            # Eski değeri geri yükle
            if old_timeout is not None:
                if 'postgresql' in engine.lower():
                    with connection.cursor() as cursor:
                        cursor.execute(f"SET lock_timeout = '{old_timeout}'")
                elif 'mysql' in engine.lower():
                    with connection.cursor() as cursor:
                        cursor.execute(f"SET innodb_lock_wait_timeout = {old_timeout}")
        except Exception:
            # Cleanup hatası kritik değil
            pass

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, IsOnActiveShift]
    pagination_class = StandardResultsSetPagination

    queryset = Order.objects.all().prefetch_related(
        Prefetch('order_items', queryset=OrderItem.objects.select_related('menu_item__category__assigned_kds', 'item_prepared_by_staff', 'variant').prefetch_related('extras__variant')),
        'table_users',
        'payment_info',
        'credit_payment_details',
        'assigned_pager_instance',
    ).select_related('table', 'customer', 'business', 'taken_by_staff', 'prepared_by_kitchen_staff')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        business_instance = get_user_business(user)
        if business_instance:
            context['business_from_context'] = business_instance
        else:
            logger.warning(f"OrderViewSet.get_serializer_context: Kullanıcı {user} için 'business_from_context' set edilemedi.")
        return context

    def get_queryset(self):
        user = self.request.user
        base_queryset = self.queryset

        business_instance = get_user_business(user)
        if not business_instance:
            if not user.is_superuser:
                return Order.objects.none()
            queryset = base_queryset
        else:
            queryset = base_queryset.filter(business=business_instance)
        
        is_paid_param = self.request.query_params.get('is_paid')
        order_type_param = self.request.query_params.get('order_type')
        exclude_status_param = self.request.query_params.get('exclude_status')
        status_param = self.request.query_params.get('status')
        table_id_param = self.request.query_params.get('table_id')

        if is_paid_param is not None:
            is_paid_bool = is_paid_param.lower() == 'true'
            queryset = queryset.filter(is_paid=is_paid_bool)
            if is_paid_bool:
                queryset = queryset.filter(status=Order.STATUS_COMPLETED)
        
        if order_type_param:
            queryset = queryset.filter(order_type=order_type_param)
            
        if exclude_status_param:
            exclude_list = [status.strip() for status in exclude_status_param.split(',')]
            if exclude_list:
                queryset = queryset.exclude(status__in=exclude_list)
        
        if status_param:
            status_list = [s.strip() for s in status_param.split(',') if s.strip()]
            if status_list:
                queryset = queryset.filter(status__in=status_list)

        if table_id_param:
            try:
                queryset = queryset.filter(table_id=int(table_id_param))
            except (ValueError, TypeError):
                return Order.objects.none()
        
        if is_paid_param is None and order_type_param is None and status_param is None:
            queryset = queryset.filter(
                is_paid=False, 
                credit_payment_details__isnull=True
            ).exclude(
                status__in=[Order.STATUS_REJECTED, Order.STATUS_CANCELLED, Order.STATUS_COMPLETED]
            )

        return queryset.order_by('-created_at')

    @transaction.atomic
    def perform_create(self, serializer):
        try:
            with handle_db_lock_timeout():
                order = serializer.save(taken_by_staff=self.request.user)
                transaction.on_commit(
                    lambda: send_order_update_notification(
                        order=order, 
                        created=True
                    )
                )
        except Exception as e:
            logger.error(f"[PERFORM_CREATE_ORDER] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            raise

    @action(detail=True, methods=['post'], url_path='add-item')
    @transaction.atomic
    def add_item(self, request, pk=None):
        """Race condition koruması ile item ekleme"""
        try:
            with handle_db_lock_timeout():
                # SELECT FOR UPDATE ile order'ı kilitle
                order = Order.objects.select_for_update().get(id=pk)
                return item_actions.add_item_action(self, request, pk=pk)
        except Order.DoesNotExist:
            raise NotFound('Sipariş bulunamadı.')
        except Exception as e:
            logger.error(f"[ADD_ITEM] Race condition hatası: {e}")
            raise ValidationError("Sipariş güncellenirken bir hata oluştu. Lütfen tekrar deneyin.")

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        assert lookup_url_kwarg in self.kwargs, (
            'Expected view %s to be called with a URL keyword argument named "%s". '
            'Fix your URL conf, or set the `.lookup_field` attribute on the view.' %
            (self.__class__.__name__, lookup_url_kwarg)
        )
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        try:
            obj = self.queryset.get(**filter_kwargs)
        except Order.DoesNotExist:
            raise NotFound('Sipariş bulunamadı veya bu işletmeye ait değil.')

        user = self.request.user
        if not (getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)):
            user_business = get_user_business(user)
            if not user_business or obj.business != user_business:
                raise PermissionDenied("Bu siparişe erişim yetkiniz yok.")
        
        self.check_object_permissions(self.request, obj)
        return obj

    def _check_order_modifiable(self, order: Order, action_name: str = "Bu işlem"):
        """Siparişin değiştirilebilir olup olmadığını kontrol eden yardımcı metot."""
        allowed_actions_for_paid_order = ["retrieve", "list", "perform_destroy", "print_bill_action"]
        if order.is_paid and getattr(self, 'action', '') not in allowed_actions_for_paid_order:
            raise PermissionDenied(f"Ödenmiş siparişler üzerinde '{action_name}' yapılamaz.")

        final_statuses = [Order.STATUS_REJECTED, Order.STATUS_CANCELLED, Order.STATUS_COMPLETED]
        if order.status in final_statuses and getattr(self, 'action', '') not in allowed_actions_for_paid_order:
            raise PermissionDenied(f"'{order.get_status_display()}' durumundaki siparişler üzerinde '{action_name}' yapılamaz.")
        
        allowed_actions_for_pending_approval = [
            'approve_guest_order', 'reject_guest_order', 
            'retrieve', 'list', 'perform_destroy', 'add_item'
        ]
        current_view_action_name = getattr(self, 'action', None)

        if order.status == Order.STATUS_PENDING_APPROVAL:
            if action_name not in allowed_actions_for_pending_approval and \
               current_view_action_name not in allowed_actions_for_pending_approval:
                raise PermissionDenied(f"'{action_name}' için siparişin önce onaylanması veya reddedilmesi gerekir.")

    @transaction.atomic
    def _add_or_update_order_item_internal(self, order: Order, item_data: dict, is_awaiting_staff_approval_flag: bool):
        from collections import Counter
        
        # SELECT FOR UPDATE ile concurrent access'i engelle
        order = Order.objects.select_for_update().get(id=order.id)
        
        menu_item = item_data.get('menu_item')
        variant = item_data.get('variant')
        quantity_to_add = item_data.get('quantity', 1)
        table_user = item_data.get('table_user')
        valid_extras_data = item_data.get('valid_extras', [])

        if not menu_item:
            logger.error(f"[ADD_ITEM_INTERNAL] Order {order.id}: MenuItem instance is missing in item_data.")
            return None

        incoming_extras_counter = Counter((extra['variant'].id, extra.get('quantity', 1)) for extra in valid_extras_data)
        
        found_item_to_increment = None
        create_new_item_instead = False

        if order.order_type == 'table':
            matching_items_query = order.order_items.select_for_update().filter(
                menu_item=menu_item,
                variant_id=variant.id if variant else None,
                table_user=table_user,
                is_awaiting_staff_approval=is_awaiting_staff_approval_flag
            ).prefetch_related('extras__variant')

            for existing_item in matching_items_query:
                existing_extras_counter = Counter((extra.variant_id, extra.quantity) for extra in existing_item.extras.all())
                if existing_extras_counter == incoming_extras_counter:
                    non_mergeable_kds_statuses = [
                        OrderItem.KDS_ITEM_STATUS_CHOICES[1][0], # preparing_kds
                        OrderItem.KDS_ITEM_STATUS_CHOICES[2][0], # ready_kds
                    ]
                    
                    if existing_item.delivered or existing_item.kds_status in non_mergeable_kds_statuses:
                        create_new_item_instead = True
                        logger.info(f"OrderItem ID {existing_item.id} (Order {order.id}): Eşleşen kalem bulundu ancak durumu birleştirmeye uygun değil (Durum: {existing_item.kds_status}, Teslim: {existing_item.delivered}). Yeni kalem oluşturulacak.")
                        break
                    else:
                        found_item_to_increment = existing_item
                        logger.info(f"OrderItem ID {existing_item.id} (Order {order.id}): Miktar artırımı için uygun bulundu.")
                        break
        else:
            create_new_item_instead = True
            logger.info(f"Order ID {order.id}: Paket sipariş olduğu için yeni ürün ekleniyor, birleştirme yapılmıyor.")
            
        main_price_decimal = variant.price if variant else Decimal('0.00')
        if menu_item.is_campaign_bundle and hasattr(menu_item, 'represented_campaign') and menu_item.represented_campaign:
            main_price_decimal = menu_item.represented_campaign.campaign_price
        
        extras_total_price_decimal = sum(
            extra_data['variant'].price * Decimal(str(extra_data.get('quantity', 1)))
            for extra_data in valid_extras_data if isinstance(extra_data.get('variant'), MenuItemVariant)
        )
        item_price_per_unit = main_price_decimal + extras_total_price_decimal

        if found_item_to_increment and not create_new_item_instead:
            found_item_to_increment.quantity += quantity_to_add
            found_item_to_increment.price = item_price_per_unit
            found_item_to_increment.save(update_fields=['quantity', 'price'])
            processed_item = found_item_to_increment
        else:
            kds_status_for_new_item = OrderItem.KDS_ITEM_STATUS_CHOICES[0][0] if menu_item.category and menu_item.category.assigned_kds else None
            order_item_instance = OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                variant_id=variant.id if variant else None,
                quantity=quantity_to_add,
                table_user=table_user,
                price=item_price_per_unit,
                is_awaiting_staff_approval=is_awaiting_staff_approval_flag,
                kds_status=kds_status_for_new_item,
                delivered=False
            )
            for extra_data in valid_extras_data:
                if isinstance(extra_data.get('variant'), MenuItemVariant):
                    OrderItemExtra.objects.create(
                        order_item=order_item_instance,
                        variant=extra_data['variant'],
                        quantity=extra_data.get('quantity', 1)
                    )
            processed_item = order_item_instance

        return OrderItem.objects.select_related(
            'menu_item__category__assigned_kds', 
            'item_prepared_by_staff',
            'variant'
        ).prefetch_related('extras__variant').get(id=processed_item.id)

    @action(detail=True, methods=['post'], url_path='deliver-item')
    @transaction.atomic
    def deliver_item(self, request, pk=None):
        return item_actions.deliver_item_action(self, request, pk=pk)

    @action(detail=True, methods=['post'], url_path='approve-guest-order')
    @transaction.atomic
    def approve_guest_order(self, request, pk=None):
        return status_actions.approve_guest_order_action(self, request, pk=pk)

    @action(detail=True, methods=['post'], url_path='reject-guest-order')
    @transaction.atomic
    def reject_guest_order(self, request, pk=None):
        return status_actions.reject_guest_order_action(self, request, pk=pk)
    
    @action(detail=True, methods=['post'], url_path='mark-picked-up-by-waiter')
    @transaction.atomic
    def mark_picked_up_by_waiter(self, request, pk=None):
        return status_actions.mark_order_picked_up_by_waiter_action(self, request, pk=pk)

    @action(detail=True, methods=['post'], url_path='deliver') 
    @transaction.atomic
    def deliver_all_items(self, request, pk=None):
        return status_actions.deliver_all_items_action(self, request, pk=pk)

    @action(detail=True, methods=['post'], url_path='mark-as-paid')
    @transaction.atomic
    def mark_as_paid(self, request, pk=None):
        return financial_actions.mark_as_paid_action(self, request, pk=pk)

    @action(detail=True, methods=['post'], url_path='credit')
    @transaction.atomic
    def save_credit_payment(self, request, pk=None):
        return financial_actions.save_credit_payment_action(self, request, pk=pk)

    @action(detail=False, methods=['get'], url_path='credit-sales')
    def list_credit_sales(self, request):
        return financial_actions.list_credit_sales_action(self, request)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        return operational_actions.destroy_order_action(self, instance)

    @action(detail=False, methods=['post'], url_path='transfer')
    @transaction.atomic
    def transfer_order(self, request):
        return operational_actions.transfer_order_action(self, request)

    @action(detail=True, methods=['post'], url_path='initiate-qr-payment')
    @transaction.atomic
    def initiate_qr_payment(self, request, pk=None):
        return financial_actions.initiate_qr_payment_action(self, request, pk=pk)

    @action(detail=True, methods=['get'], url_path='check-qr-payment-status')
    def check_qr_payment_status(self, request, pk=None):
        return financial_actions.check_qr_payment_status_action(self, request, pk=pk)


class OrderItemViewSet(mixins.DestroyModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated, IsOnActiveShift]
    
    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)
        if not user_business:
            if not (getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)):
                return OrderItem.objects.none()
            return OrderItem.objects.all().select_related('order__business', 'menu_item', 'item_prepared_by_staff', 'variant').prefetch_related('extras__variant')
        return OrderItem.objects.filter(order__business=user_business).select_related('order__business', 'menu_item', 'item_prepared_by_staff', 'variant').prefetch_related('extras__variant')
    
    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        user_business = get_user_business(user)
        can_access = False
        if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
            can_access = True
        elif user_business and obj.order.business == user_business:
            can_access = True
        
        if not can_access:
            raise PermissionDenied("Bu sipariş kaleminine erişim yetkiniz yok.")
        return obj

    def _check_order_item_modifiable(self, order_item: OrderItem, action_name: str = "Bu işlem"):
        order = order_item.order
        if order.is_paid:
            raise PermissionDenied("Ödenmiş siparişin kalemleri üzerinde bu işlem yapılamaz.")
        
        if order_item.is_awaiting_staff_approval and order.status == Order.STATUS_PENDING_APPROVAL:
            if action_name not in ["retrieve", "list", "destroy_item_action_for_approval"]:
                raise PermissionDenied(f"Bu kalem personel onayı bekliyor ve sipariş genel onaya tabi. '{action_name}' yapılamaz.")

        final_statuses = [Order.STATUS_REJECTED, Order.STATUS_CANCELLED, Order.STATUS_COMPLETED]
        if order.status in final_statuses and not order_item.is_awaiting_staff_approval:
            raise PermissionDenied(f"'{order.get_status_display()}' durumundaki siparişin onaylanmış kalemleri için '{action_name}' yapılamaz.")

    @transaction.atomic
    def perform_update(self, serializer):
        order_item = serializer.instance 
        user = self.request.user

        if not (user.user_type == 'business_owner' or
                (user.user_type == 'staff' and PermissionKeys.TAKE_ORDERS in user.staff_permissions)):
            raise PermissionDenied("Sipariş kalemi güncelleme yetkiniz yok.")
        
        self._check_order_item_modifiable(order_item, action_name="güncelleme")

        with handle_db_lock_timeout():
            # SELECT FOR UPDATE ile order item'ı kilitle
            order_item = OrderItem.objects.select_for_update().get(id=order_item.id)
            
            allowed_update_fields = {'quantity', 'delivered'}
            update_data = {}
            has_valid_update = False

            for field in allowed_update_fields:
                if field in serializer.validated_data:
                    if field == 'quantity':
                        new_quantity = serializer.validated_data[field]
                        if new_quantity <= 0:
                            raise ValidationError({"quantity": "Miktar pozitif olmalıdır. Kalemi silmek için silme endpoint'ini kullanın."})
                        if new_quantity != order_item.quantity:
                            update_data[field] = new_quantity
                            has_valid_update = True
                    elif field == 'delivered':
                        if serializer.validated_data[field] != order_item.delivered:
                            update_data[field] = serializer.validated_data[field]
                            has_valid_update = True
            
            if not has_valid_update:
                return Response(OrderSerializer(order_item.order, context={'request': self.request}).data, status=status.HTTP_200_OK)

            for field, value in update_data.items():
                setattr(order_item, field, value)
            
            if 'delivered' in update_data and update_data['delivered'] == True:
                if order_item.kds_status != OrderItem.KDS_ITEM_STATUS_CHOICES[2][0]: 
                    logger.warning(f"OrderItem ID {order_item.id} teslim edildi olarak işaretlendi ancak KDS durumu '{order_item.kds_status}'.")
            
            order_item.save(update_fields=list(update_data.keys()))
            updated_item = order_item
            logger.info(f"OrderItem ID {updated_item.id} güncellendi. Değişen alanlar: {update_data.keys()}")

            order = updated_item.order
            order.refresh_from_db() 
            
            all_items_delivered = not order.order_items.filter(delivered=False).exists()
            order_updated_main_fields = []
            if all_items_delivered and order.delivered_at is None:
                order.delivered_at = timezone.now()
                order_updated_main_fields.append('delivered_at')
                logger.info(f"OrderItem güncellemesi sonucu Order ID {order.id} tamamen teslim edildi olarak işaretlendi.")
            
            if order_updated_main_fields:
                order.save(update_fields=order_updated_main_fields)

        final_order_serializer = OrderSerializer(order, context={'request': self.request})
        
        # GÜNCELLEME: Payload yapısı, message_params yerine message_args (dictionary) kullanacak şekilde değiştirildi.
        try:
            from makarna_project.asgi import sio
            if sio:
                room_name = f'business_{order.business.id}'
                payload = {
                    'event_type': 'order_item_updated',
                    'message_key': 'notificationOrderItemUpdated',
                    'message_args': {
                        'orderId': str(order.id),
                        'productName': updated_item.menu_item.name
                    },
                    'updated_order_data': convert_decimals_to_strings(final_order_serializer.data),
                }
                async_to_sync(sio.emit)('order_status_update', payload, room=room_name)
        except Exception as e_socket:
            logger.error(f"Socket.IO olayı gönderilirken hata (OrderItem update - sipariş {order.id}): {e_socket}", exc_info=True)
        
        return Response(final_order_serializer.data, status=status.HTTP_200_OK)

    @transaction.atomic
    def perform_destroy(self, instance: OrderItem):
        user = self.request.user
        if not (user.user_type == 'business_owner' or \
                (user.user_type == 'staff' and PermissionKeys.TAKE_ORDERS in user.staff_permissions) or \
                user.is_superuser):
            raise PermissionDenied("Sipariş kalemi silme yetkiniz yok.")

        self._check_order_item_modifiable(instance, action_name="silme") 
        
        with handle_db_lock_timeout():
            # SELECT FOR UPDATE ile instance'ı ve order'ı kilitle
            instance = OrderItem.objects.select_for_update().select_related('order').get(id=instance.id)
            order = Order.objects.select_for_update().get(id=instance.order.id)
            
            order_id_for_log = order.id
            business_id_for_log = order.business.id
            table_id_for_log = order.table.id if order.table else None
            removed_item_id_for_log = instance.id
            item_name_for_log = instance.menu_item.name
            
            is_last_item = order.order_items.count() == 1
            
            instance.delete()
            logger.info(f"OrderItem ID {removed_item_id_for_log} ({item_name_for_log}) from Order ID {order_id_for_log} deleted by user {user.username}.")

            try:
                order.refresh_from_db()
                order_serializer_data = OrderSerializer(order, context={'request': self.request}).data
                
                # GÜNCELLEME: Bildirim payload yapısı, message_params yerine message_args (dictionary) kullanacak şekilde değiştirildi.
                event_type = 'order_item_removed'
                message_key = 'notificationOrderItemRemoved'
                message_args = {
                    'orderId': str(order_id_for_log),
                    'productName': item_name_for_log
                }

                if is_last_item and order.order_items.count() == 0 and \
                   order.status not in [Order.STATUS_COMPLETED, Order.STATUS_CANCELLED, Order.STATUS_REJECTED]:
                    order.status = Order.STATUS_CANCELLED
                    order.save(update_fields=['status'])
                    logger.info(f"Order ID {order_id_for_log} (son kalemi silindiği için) İPTAL EDİLDİ olarak işaretlendi.")
                    order_serializer_data = OrderSerializer(order, context={'request': self.request}).data
                    
                    event_type = 'order_cancelled'
                    message_key = 'notificationOrderCancelledAllItemsRemoved'
                    message_args = {'orderId': str(order_id_for_log)}
                
                try:
                    from makarna_project.asgi import sio
                    if sio:
                        room_name = f'business_{business_id_for_log}'
                        payload = {
                            'event_type': event_type,
                            'message_key': message_key,
                            'message_args': message_args, # Değiştirildi: message_params -> message_args
                            'updated_order_data': convert_decimals_to_strings(order_serializer_data),
                        }
                        async_to_sync(sio.emit)('order_status_update', payload, room=room_name)
                        logger.info(f"Socket.IO olayı ({event_type}) Order ID {order_id_for_log} için {room_name} odasına gönderildi.")
                except Exception as e_socket:
                    logger.error(f"Socket.IO olayı gönderilirken hata (OrderItem delete - sipariş {order_id_for_log}): {e_socket}", exc_info=True)

            except Order.DoesNotExist:
                logger.warning(f"Order ID {order_id_for_log} bulunamadı (OrderItem silindikten sonra).")
                try:
                    from makarna_project.asgi import sio
                    if sio:
                        room_name = f'business_{business_id_for_log}'
                        payload = {
                            'event_type': 'order_deleted', 
                            'order_id': order_id_for_log, 
                            'table_id': table_id_for_log, 
                            'business_id': business_id_for_log 
                        }
                        async_to_sync(sio.emit)('order_status_update', payload, room=room_name)
                except Exception as e_socket:
                    logger.error(f"Socket.IO olayı gönderilirken hata (Order not found - sipariş {order_id_for_log}): {e_socket}", exc_info=True)

    @action(detail=True, methods=['post'], url_path='start-preparing')
    @transaction.atomic
    def start_preparing_item(self, request, pk=None):
        order_item = self.get_object()
        order = order_item.order
        self._check_order_item_modifiable(order_item, "hazırlamaya başlama")

        with handle_db_lock_timeout():
            # SELECT FOR UPDATE ile kilitle
            order_item = OrderItem.objects.select_for_update().get(id=order_item.id)
            order = Order.objects.select_for_update().get(id=order.id)

            if order_item.kds_status != OrderItem.KDS_ITEM_STATUS_CHOICES[0][0]: # 'pending_kds'
                return Response({'detail': 'Bu ürün zaten hazırlanıyor veya hazır durumda.'}, status=status.HTTP_400_BAD_REQUEST)

            order_item.kds_status = OrderItem.KDS_ITEM_STATUS_CHOICES[1][0] # 'preparing_kds'
            order_item.item_prepared_by_staff = request.user
            order_item.save(update_fields=['kds_status', 'item_prepared_by_staff'])

            if order.status == Order.STATUS_APPROVED:
                order.status = Order.STATUS_PREPARING
                order.save(update_fields=['status'])

            logger.info(f"OrderItem ID {order_item.id} (Order #{order.id}) 'preparing_kds' olarak işaretlendi.")
            
            transaction.on_commit(
                lambda: send_order_update_notification(
                    order=order, 
                    created=False, 
                    specific_event_type='order_preparing_update'
                )
            )
            
            serializer = OrderSerializer(order_item.order, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='mark-ready')
    @transaction.atomic
    def mark_item_ready(self, request, pk=None):
        order_item = self.get_object()
        order = order_item.order
        self._check_order_item_modifiable(order_item, "hazır olarak işaretleme")

        with handle_db_lock_timeout():
            # SELECT FOR UPDATE ile kilitle
            order_item = OrderItem.objects.select_for_update().get(id=order_item.id)
            order = Order.objects.select_for_update().get(id=order.id)

            if order_item.kds_status == OrderItem.KDS_ITEM_STATUS_CHOICES[2][0]: # 'ready_kds'
                return Response({'detail': 'Bu ürün zaten hazır olarak işaretlenmiş.'}, status=status.HTTP_400_BAD_REQUEST)

            order_item.kds_status = OrderItem.KDS_ITEM_STATUS_CHOICES[2][0] # 'ready_kds'
            if not order_item.item_prepared_by_staff:
                order_item.item_prepared_by_staff = request.user
            order_item.save(update_fields=['kds_status', 'item_prepared_by_staff'])
            logger.info(f"OrderItem ID {order_item.id} (Order #{order.id}) 'ready_kds' olarak işaretlendi.")

            all_kds_items_in_order = order.order_items.filter(
                is_awaiting_staff_approval=False, 
                delivered=False, 
                menu_item__category__assigned_kds__isnull=False
            )
            
            all_ready = not all_kds_items_in_order.exclude(kds_status=OrderItem.KDS_ITEM_STATUS_READY).exists()

            notification_event_to_send = None
            
            if all_ready:
                logger.info(f"Sipariş #{order.id} için tüm KDS ürünleri hazır. Genel durum güncelleniyor.")
                if order.status != Order.STATUS_READY_FOR_PICKUP:
                    order.status = Order.STATUS_READY_FOR_PICKUP
                    order.kitchen_completed_at = timezone.now()
                    order.save(update_fields=['status', 'kitchen_completed_at'])
                
                notification_event_to_send = 'order_ready_for_pickup_update'
            else:
                logger.info(f"Sipariş #{order.id} için bazı kalemler hazır, ancak diğerleri bekliyor.")
                notification_event_to_send = 'order_item_updated'
            
            transaction.on_commit(
                lambda: send_order_update_notification(
                    order=order, 
                    created=False, 
                    specific_event_type=notification_event_to_send
                )
            )
            
            serializer = OrderSerializer(order_item.order, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='mark-picked-up')
    @transaction.atomic
    def mark_item_picked_up(self, request, pk=None):
        """Tek bir sipariş kalemini garson tarafından alınmış olarak işaretler."""
        order_item = self.get_object()
        order = order_item.order
        self._check_order_item_modifiable(order_item, "garson tarafından alınma")

        with handle_db_lock_timeout():
            # SELECT FOR UPDATE ile kilitle
            order_item = OrderItem.objects.select_for_update().get(id=order_item.id)
            order = Order.objects.select_for_update().get(id=order.id)

            if order_item.kds_status != OrderItem.KDS_ITEM_STATUS_CHOICES[2][0]: # 'ready_kds'
                return Response(
                    {'detail': f"Bu ürün henüz mutfakta hazır değil. Durum: {order_item.get_kds_status_display()}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            order_item.kds_status = OrderItem.KDS_ITEM_STATUS_CHOICES[3][0] # 'picked_up_kds'
            order_item.waiter_picked_up_at = timezone.now()
            order_item.save(update_fields=['kds_status', 'waiter_picked_up_at'])
            logger.info(f"OrderItem ID {order_item.id} (Order #{order.id}) 'picked_up_kds' olarak işaretlendi.")

            if order.status == Order.STATUS_READY_FOR_PICKUP:
                order.status = Order.STATUS_READY_FOR_DELIVERY
                if not order.picked_up_by_waiter_at:
                    order.picked_up_by_waiter_at = timezone.now()
                order.save(update_fields=['status', 'picked_up_by_waiter_at'])
                transaction.on_commit(lambda: send_order_update_notification(order=order, created=False, update_fields=['status', 'order_items']))
            else:
                transaction.on_commit(lambda: send_order_update_notification(order=order, created=False, update_fields=['order_items']))

            order.refresh_from_db()
            return Response(OrderSerializer(order, context=self.get_serializer_context()).data, status=status.HTTP_200_OK)