# core/views/kds_views.py

# makarna_project/core/views/kds_views.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from django.utils import timezone
from django.db import transaction, models
import logging
import json
from django.db.models import Prefetch, Q, Exists, OuterRef
from decimal import Decimal

from ..models import Order, CustomUser, OrderItem, CreditPaymentDetails, KDSScreen, Business, Category
from ..serializers import KDSOrderSerializer
from ..utils.order_helpers import get_user_business, PermissionKeys
# GÜNCELLENDİ: Artık order nesnesi ile çağrılacak
from ..signals.order_signals import send_order_update_notification

logger = logging.getLogger(__name__)

def convert_decimals_to_strings(obj):
    if isinstance(obj, list):
        return [convert_decimals_to_strings(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return str(obj)
    return obj

class CanAccessSpecificKDS(BasePermission):
    message = "Bu KDS ekranına erişim yetkiniz yok."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        kds_slug = view.kwargs.get('kds_slug')
        if not kds_slug:
            logger.warning(f"KDS Erişimi: kds_slug URL parametresi eksik. Kullanıcı: {user.username}")
            return False

        user_business = get_user_business(user)
        if not user_business:
            logger.warning(f"KDS Erişimi: Kullanıcı {user.username} için işletme bulunamadı.")
            return False

        try:
            kds_screen = KDSScreen.objects.get(business=user_business, slug=kds_slug, is_active=True)
            view.target_kds_screen = kds_screen
        except KDSScreen.DoesNotExist:
            logger.warning(f"KDS Erişimi: {user_business.name} işletmesinde aktif '{kds_slug}' slug'lı KDS bulunamadı. Kullanıcı: {user.username}")
            return False
        
        if user.user_type == 'business_owner':
            return True
        if user.user_type in ['staff', 'kitchen_staff']:
            staff_perms = user.staff_permissions
            if PermissionKeys.MANAGE_KDS in staff_perms and kds_screen in user.accessible_kds_screens.all():
                return True
        
        logger.warning(f"KDS Erişimi: Kullanıcı {user.username}, KDS '{kds_slug}' için yetkisiz.")
        return False


class KDSOrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = KDSOrderSerializer
    permission_classes = [IsAuthenticated, CanAccessSpecificKDS]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        if not hasattr(self, 'target_kds_screen'):
            kds_slug_from_url = self.kwargs.get('kds_slug')
            user_business_from_context = get_user_business(self.request.user)
            if kds_slug_from_url and user_business_from_context:
                try:
                    self.target_kds_screen = KDSScreen.objects.get(business=user_business_from_context, slug=kds_slug_from_url, is_active=True)
                except KDSScreen.DoesNotExist:
                    logger.warning(f"KDSOrderViewSet.get_serializer_context (fallback): KDS '{kds_slug_from_url}' not found.")
                    self.target_kds_screen = None
            else:
                self.target_kds_screen = None
        context['target_kds_screen'] = getattr(self, 'target_kds_screen', None)
        return context

    def get_queryset(self):
        user = self.request.user
        user_business = get_user_business(user)
        target_kds_screen = getattr(self, 'target_kds_screen', None)

        if not user_business or not target_kds_screen:
            return Order.objects.none()

        logger.debug(f"KDS View Query: Fetching orders for KDS '{target_kds_screen.name}' (ID: {target_kds_screen.id}), Business: '{user_business.name}' by user '{user.username}'.")
        
        relevant_orders = Order.objects.filter(
            business=user_business,
            is_paid=False,
            credit_payment_details__isnull=True,
            status__in=[Order.STATUS_APPROVED, Order.STATUS_PREPARING, Order.STATUS_READY_FOR_PICKUP]
        ).exclude(
            status__in=[Order.STATUS_COMPLETED, Order.STATUS_CANCELLED, Order.STATUS_REJECTED]
        ).annotate(
            has_actionable_items_for_this_kds=Exists(
                OrderItem.objects.filter(
                    order=OuterRef('pk'),
                    menu_item__category__assigned_kds_id=target_kds_screen.id,
                    is_awaiting_staff_approval=False,
                    delivered=False,
                    kds_status__in=[
                        OrderItem.KDS_ITEM_STATUS_CHOICES[0][0], # 'pending_kds'
                        OrderItem.KDS_ITEM_STATUS_CHOICES[1][0], # 'preparing_kds'
                    ]
                )
            )
        ).filter(has_actionable_items_for_this_kds=True).select_related(
            'table', 'customer', 'taken_by_staff', 'prepared_by_kitchen_staff', 'assigned_pager_instance'
        ).prefetch_related(
            Prefetch(
                'order_items',
                queryset=OrderItem.objects.select_related(
                    'menu_item__category__assigned_kds',
                    'menu_item__represented_campaign',
                    'item_prepared_by_staff'
                ).prefetch_related('extras__variant')
            )
        ).distinct().order_by('created_at')
        
        return relevant_orders

    @action(detail=True, methods=['post'], url_path='start-preparation')
    @transaction.atomic
    def start_preparation(self, request, kds_slug=None, pk=None):
        order = self.get_object()
        target_kds_screen = getattr(self, 'target_kds_screen', None)
        
        if not target_kds_screen:
            logger.error(f"KDS Action (start_preparation): Order #{order.id} için target_kds_screen alınamadı. User: {request.user.username}, KDS Slug: {kds_slug}")
            raise PermissionDenied("KDS bilgisi alınamadı, işlem yapılamıyor.")

        logger.info(
            f"[KDS VIEW] Action 'start_preparation' BAŞLANGIÇ: Order ID: {order.id}, "
            f"Hedef KDS: '{target_kds_screen.name}' (ID: {target_kds_screen.id}), "
            f"Kullanıcı: {request.user.username}"
        )
        
        all_items_in_order_for_debug = OrderItem.objects.filter(
            order_id=order.id, 
            is_awaiting_staff_approval=False, 
            delivered=False
        ).select_related('menu_item__category__assigned_kds', 'menu_item__category')
        logger.info(f"  [KDS VIEW] Order #{order.id} için TÜM AKTİF KALEMLER (Sorgudan Önce):")
        for item_debug in all_items_in_order_for_debug:
            cat_assigned_kds_id_debug = item_debug.menu_item.category.assigned_kds_id if item_debug.menu_item and item_debug.menu_item.category and item_debug.menu_item.category.assigned_kds else None
            logger.info(
                f"    DEBUG ITEM - ID: {item_debug.id}, Adı: '{item_debug.menu_item.name if item_debug.menu_item else 'N/A'}', "
                f"Kategorisinin KDS ID: {cat_assigned_kds_id_debug}, Mevcut KDS Durumu: '{item_debug.kds_status}'"
            )

        if order.status not in [Order.STATUS_APPROVED, Order.STATUS_PREPARING]:
            logger.warning(f"[KDS VIEW] Order #{order.id} (status: {order.get_status_display()}) 'start_preparation' için uygun değil. KDS: '{target_kds_screen.name}'")
            return Response({'detail': f"Bu siparişin durumu ('{order.get_status_display()}') hazırlanmaya başlanamaz."}, status=status.HTTP_400_BAD_REQUEST)
        
        category_ids_for_this_kds = Category.objects.filter(assigned_kds_id=target_kds_screen.id).values_list('id', flat=True)

        if not category_ids_for_this_kds:
            logger.warning(f"KDS Action (start_preparation): KDS '{target_kds_screen.name}' (ID: {target_kds_screen.id}) için atanmış kategori bulunamadı.")
            return Response(
                {'detail': f"Bu KDS ({target_kds_screen.name}) ekranı için atanmış kategori olmadığından hazırlanacak ürün bulunamadı."},
                status=status.HTTP_400_BAD_REQUEST
            )
        logger.info(f"  [KDS VIEW] KDS '{target_kds_screen.name}' için ilgili Kategori ID'leri: {list(category_ids_for_this_kds)}")

        items_to_prepare = OrderItem.objects.filter(
            order_id=order.id,
            menu_item__category_id__in=list(category_ids_for_this_kds), 
            is_awaiting_staff_approval=False,
            delivered=False,
            kds_status=OrderItem.KDS_ITEM_STATUS_CHOICES[0][0] # 'pending_kds'
        )
        
        logger.info(f"  [KDS VIEW] KDS '{target_kds_screen.name}' için 'pending_kds' durumunda bulunan ve filtrelenen ürün sayısı: {items_to_prepare.count()}")
        for itp_debug in items_to_prepare:
            logger.info(f"    -> Filtrelenmiş Hazırlanacak Ürün: ID {itp_debug.id}, Adı: {itp_debug.menu_item.name}, Kategorisinin KDS ID: {itp_debug.menu_item.category.assigned_kds_id if itp_debug.menu_item.category else 'N/A'}")

        if not items_to_prepare.exists():
            all_active_items_for_this_kds_again = OrderItem.objects.filter(
                order_id=order.id,
                menu_item__category_id__in=list(category_ids_for_this_kds),
                is_awaiting_staff_approval=False,
                delivered=False
            )
            current_statuses_for_error_debug = {item.id: f"{item.menu_item.name} ({item.kds_status})" for item in all_active_items_for_this_kds_again}
            logger.warning(
                f"KDS Action (start_preparation) - 400 Nedeni (İç Kontrol): Order #{order.id}, KDS '{target_kds_screen.name}' (ID: {target_kds_screen.id}) için 'pending_kds' "
                f"durumunda ürün bulunamadı. Bu KDS için mevcut aktif kalem durumları (tekrar kontrol): {current_statuses_for_error_debug}"
            )
            if all_active_items_for_this_kds_again.filter(kds_status__in=[OrderItem.KDS_ITEM_STATUS_CHOICES[1][0], OrderItem.KDS_ITEM_STATUS_CHOICES[2][0]]).exists():
                return Response({'detail': f"Bu KDS ({target_kds_screen.name}) ekranındaki ürünler zaten hazırlanıyor veya hazır durumda. (Durumlar: {current_statuses_for_error_debug})"}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'detail': f"Bu KDS ({target_kds_screen.name}) ekranı için hazırlanmaya başlanacak yeni ürün bulunmuyor. (Durumlar: {current_statuses_for_error_debug})"}, status=status.HTTP_400_BAD_REQUEST)

        updated_item_ids = []
        for item in items_to_prepare: 
            logger.info(
                f"  [KDS VIEW] GÜNCELLENİYOR -> Item ID {item.id} ('{item.menu_item.name}', "
                f"ItemCatKDS_ID: {item.menu_item.category.assigned_kds_id if item.menu_item.category and item.menu_item.category.assigned_kds else 'N/A'}) "
                f"için KDS '{target_kds_screen.name}' (TargetKDS_ID: {target_kds_screen.id}). "
                f"Eski KDS Durumu: '{item.kds_status}', Yeni: 'preparing_kds'."
            )
            item.kds_status = OrderItem.KDS_ITEM_STATUS_CHOICES[1][0] 
            item.item_prepared_by_staff = request.user
            item.save(update_fields=['kds_status', 'item_prepared_by_staff'])
            updated_item_ids.append(item.id)
        
        update_fields_for_notification = []
        if order.status == Order.STATUS_APPROVED and updated_item_ids:
            order.status = Order.STATUS_PREPARING
            order.save(update_fields=['status'])
            logger.info(f"[KDS VIEW] Order ID {order.id} genel durumu KDS '{target_kds_screen.name}' tarafından '{Order.STATUS_PREPARING}' olarak güncellendi.")
            update_fields_for_notification.append('status')
        
        logger.info(f"KDS '{target_kds_screen.name}': Order #{order.id} için {len(updated_item_ids)} kalem ({updated_item_ids}) 'KDS Hazırlanıyor' olarak işaretlendi by {request.user.username}")
        
        transaction.on_commit(
            lambda: send_order_update_notification(
                order=order, created=False, update_fields=update_fields_for_notification
            )
        )
        
        order.refresh_from_db()
        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='mark-ready-for-pickup')
    @transaction.atomic
    def mark_ready_for_pickup(self, request, kds_slug=None, pk=None):
        order = self.get_object()
        target_kds_screen = getattr(self, 'target_kds_screen', None)
        if not target_kds_screen:
            raise PermissionDenied("KDS bilgisi alınamadı, işlem yapılamıyor.")
        
        logger.info(
            f"[KDS VIEW] Action 'mark_ready_for_pickup' BAŞLANGIÇ: Order ID: {order.id}, "
            f"Hedef KDS: '{target_kds_screen.name}', Kullanıcı: {request.user.username}"
        )
        
        category_ids_for_this_kds = Category.objects.filter(assigned_kds_id=target_kds_screen.id).values_list('id', flat=True)

        if not category_ids_for_this_kds:
            return Response({'detail': f"Bu KDS ({target_kds_screen.name}) için atanmış kategori yok."}, status=status.HTTP_400_BAD_REQUEST)

        items_to_mark_ready = OrderItem.objects.filter(
            order_id=order.id,
            menu_item__category_id__in=list(category_ids_for_this_kds),
            is_awaiting_staff_approval=False,
            delivered=False,
            kds_status__in=[OrderItem.KDS_ITEM_STATUS_PENDING, OrderItem.KDS_ITEM_STATUS_PREPARING]
        )

        if not items_to_mark_ready.exists():
            return Response({'detail': 'Bu KDS için hazır olarak işaretlenecek aktif ürün bulunmuyor.'}, status=status.HTTP_400_BAD_REQUEST)

        updated_item_count = items_to_mark_ready.update(
            kds_status=OrderItem.KDS_ITEM_STATUS_READY,
            item_prepared_by_staff=request.user
        )
        logger.info(f"KDS '{target_kds_screen.name}': Order #{order.id} için {updated_item_count} kalem 'KDS Hazır' olarak işaretlendi.")

        # Siparişteki KDS ile ilgili TÜM ürünleri tekrar sorgula
        all_kds_relevant_items = OrderItem.objects.filter(
            order=order,
            is_awaiting_staff_approval=False,
            delivered=False,
            menu_item__category__assigned_kds__isnull=False
        )
        
        # Eğer KDS'e ait başka ürün kalmadıysa veya hepsi hazırsa, siparişin genel durumunu güncelle
        all_items_globally_ready = not all_kds_relevant_items.exclude(kds_status=OrderItem.KDS_ITEM_STATUS_READY).exists()
        
        if all_items_globally_ready:
            # Tüm ürünler hazır, siparişin genel durumunu güncelle
            if order.status != Order.STATUS_READY_FOR_PICKUP:
                order.status = Order.STATUS_READY_FOR_PICKUP
                order.kitchen_completed_at = timezone.now()
                order.save(update_fields=['status', 'kitchen_completed_at'])
                logger.info(f"Order ID {order.id} tüm KDS kalemleri hazır olduğu için durumu '{Order.STATUS_READY_FOR_PICKUP}' olarak güncellendi.")
                
                # Belirgin ve DOĞRU bildirimi gönder
                transaction.on_commit(
                    lambda: send_order_update_notification(
                        order=order, created=False, update_fields=['status', 'kitchen_completed_at']
                    )
                )
        else:
            # Siparişin sadece bir kısmı hazır, genel durumu değiştirme.
            # Sadece NÖTR bir güncelleme bildirimi gönder ki ekranlar veriyi yenilesin.
            logger.info(f"Order ID {order.id} için bazı kalemler hazır, ancak diğer KDS'lerde bekleyenler var. Sadece genel güncelleme bildirimi gönderilecek.")
            transaction.on_commit(
                lambda: send_order_update_notification(
                    order=order, 
                    created=False, 
                    specific_event_type='order_updated' # <-- ANAHTAR DEĞİŞİKLİK
                )
            )
            
        order.refresh_from_db()
        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)