# core/permissions.py

from rest_framework.permissions import BasePermission
from .utils.order_helpers import get_user_business, PermissionKeys
from .models import (
    KDSScreen, CustomUser, Business, ScheduledShift, MenuItem, MenuItemVariant,
    Order, OrderItem, CampaignMenu, Stock
)
from django.utils import timezone
from datetime import timedelta
import pytz  # Zaman dilimi işlemleri için eklendi
import logging

logger = logging.getLogger(__name__)

class IsBusinessOwner(BasePermission):
    """
    Allows access only to users who are business owners.
    """
    message = "Bu işlem için işletme sahibi olmanız gerekmektedir."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.user_type == 'business_owner'

class IsBusinessOwnerAndOwnerOfObject(BasePermission):
    """
    Allows access only to business owners for objects belonging to their business,
    or to superusers.
    Assumes the object has a 'business' attribute, or an indirect way to get to it.
    """
    message = "Bu nesne üzerinde işlem yapma yetkiniz yok veya nesne sizin işletmenize ait değil."

    def _get_object_business(self, obj):
        # Direct business attribute
        if hasattr(obj, 'business') and obj.business is not None:
            return obj.business
        # For MenuItemVariant (via menu_item)
        elif isinstance(obj, MenuItemVariant) and hasattr(obj, 'menu_item') and hasattr(obj.menu_item, 'business') and obj.menu_item.business is not None:
            return obj.menu_item.business
        # For Stock (via variant -> menu_item -> business)
        elif isinstance(obj, Stock) and hasattr(obj, 'variant') and hasattr(obj.variant, 'menu_item') and \
             hasattr(obj.variant.menu_item, 'business') and obj.variant.menu_item.business is not None:
            return obj.variant.menu_item.business
        # For OrderItem (via order -> business)
        elif isinstance(obj, OrderItem) and hasattr(obj, 'order') and hasattr(obj.order, 'business') and obj.order.business is not None:
            return obj.order.business
        # For OrderTableUser (via order -> business)
        elif hasattr(obj, 'order') and hasattr(obj.order, 'business') and obj.order.business is not None: # OrderItem ile aynı mantık
            return obj.order.business
        # For CampaignMenuItem (via campaign_menu -> business)
        elif isinstance(obj, CampaignMenu) and hasattr(obj, 'business') and obj.business is not None:
            return obj.business
        # For CampaignMenuItem (via campaign_menu -> business)
        elif hasattr(obj, 'campaign_menu') and hasattr(obj.campaign_menu, 'business') and obj.campaign_menu.business is not None:
            return obj.campaign_menu.business
        # For StaffUser (CustomUser modelinde associated_business alanı)
        elif isinstance(obj, CustomUser) and obj.user_type in ['staff', 'kitchen_staff'] and obj.associated_business is not None:
            return obj.associated_business
        # For CustomUser as business_owner (owned_business üzerinden)
        elif isinstance(obj, CustomUser) and obj.user_type == 'business_owner' and hasattr(obj, 'owned_business') and obj.owned_business is not None:
            return obj.owned_business

        logger.warning(f"IsBusinessOwnerAndOwnerOfObject: Could not determine business for object {obj} of type {type(obj)}")
        return None

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        user_business = get_user_business(request.user)
        if not user_business:
            return False

        object_business = self._get_object_business(obj)
        if not object_business:
            return False
            
        return object_business == user_business

class IsBusinessOwnerAndOwnerOfStaff(BasePermission):
    """
    Allows access only to business owners for staff members belonging to their business,
    or to superusers.
    Assumes the 'obj' is a CustomUser instance representing a staff member.
    """
    message = "Bu personel üzerinde işlem yapma yetkiniz yok veya personel sizin işletmenize ait değil."

    def has_object_permission(self, request, view, obj: CustomUser): # Tip ipucu eklendi
        if request.user.is_superuser:
            return True

        if request.user.user_type != 'business_owner':
            return False
            
        user_business = get_user_business(request.user)
        if not user_business:
            return False

        if hasattr(obj, 'user_type'): # obj bir CustomUser ise
            if obj.user_type in ['staff', 'kitchen_staff'] and hasattr(obj, 'associated_business') and obj.associated_business == user_business:
                return True
            if obj.user_type == 'business_owner' and hasattr(obj, 'owned_business') and obj.owned_business == user_business:
                return True
        elif isinstance(obj, CampaignMenu):
            return obj.business == user_business
        elif isinstance(obj, MenuItem):
            return obj.business == user_business
        elif isinstance(obj, MenuItemVariant):
            return obj.menu_item.business == user_business
        
        logger.warning(f"IsBusinessOwnerAndOwnerOfStaff: Permission denied for user {request.user} on object {obj} of type {type(obj)}. User Business: {user_business}, Object relevant business: {getattr(obj, 'associated_business', None) or getattr(obj, 'owned_business', None) or getattr(obj, 'business', None)}")
        return False


class IsStaffOfAssociatedBusiness(BasePermission):
    """
    Allows access only to staff members for objects belonging to their associated business,
    or to business owners of that business, or to superusers.
    """
    message = "Bu işlem için yetkili personel olmanız veya nesnenin sizin işletmenize ait olması gerekmektedir."

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        user = request.user
        user_business = get_user_business(user)

        if not user_business:
            return False

        object_business = None
        if hasattr(obj, 'business'):
            object_business = obj.business
        elif hasattr(obj, 'menu_item') and hasattr(obj.menu_item, 'business'):
            object_business = obj.menu_item.business
        elif hasattr(obj, 'variant') and hasattr(obj.variant, 'menu_item') and hasattr(obj.variant.menu_item, 'business'):
             object_business = obj.variant.menu_item.business
        elif isinstance(obj, CustomUser) and obj.user_type in ['staff', 'kitchen_staff']:
            object_business = obj.associated_business
        elif isinstance(obj, CustomUser) and obj.user_type == 'business_owner' and hasattr(obj, 'owned_business'):
            object_business = obj.owned_business

        if not object_business:
            logger.warning(f"IsStaffOfAssociatedBusiness: Could not determine business for object {obj} of type {type(obj)}")
            return False

        return object_business == user_business


class CanManageSpecificKDS(BasePermission):
    """
    Allows access if the user is the business owner of the KDS screen's business
    OR if the user is staff and has this specific KDS screen in their accessible_kds_screens.
    """
    message = "Bu KDS ekranını yönetme veya görüntüleme yetkiniz yok."

    def has_object_permission(self, request, view, obj: KDSScreen):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        user_business = get_user_business(request.user)

        if obj.business != user_business:
            return False

        if request.user.user_type == 'business_owner':
            return True
            
        if request.user.user_type in ['staff', 'kitchen_staff']:
            if PermissionKeys.MANAGE_KDS in request.user.staff_permissions or \
               obj in request.user.accessible_kds_screens.all():
                return True
            
        return False


# --- GÜNCELLENMİŞ VE DOĞRU ÇALIŞAN YETKİ SINIFI ---
class IsOnActiveShift(BasePermission):
    """
    Sadece kendisine o an için aktif bir vardiya atanmış personelin
    kritik işlemleri (örn: sipariş alma) yapmasına izin verir.
    Kontrolü, personelin bağlı olduğu işletmenin yerel zaman dilimine göre yapar.
    """
    message = "Bu işlemi gerçekleştirmek için aktif bir vardiyada olmanız gerekmektedir."

    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
            
        # İşletme sahibi, admin veya müşteri için bu kontrolü atla
        if user.user_type not in ['staff', 'kitchen_staff']:
            return True 
        
        # Superuser her zaman yetkilidir
        if user.is_superuser:
            return True

        # Personelin bağlı olduğu işletmeyi bul
        business = getattr(user, 'associated_business', None)
        if not business:
            # Bu durum normalde olmamalı ama bir güvenlik önlemi
            return False

        # İşletmenin zaman dilimini al, yoksa varsayılanı kullan
        try:
            business_tz = pytz.timezone(business.timezone)
        except pytz.UnknownTimeZoneError:
            business_tz = timezone.get_current_timezone()

        # Sunucunun saatini (UTC) işletmenin yerel saatine çevir
        now_in_business_tz = timezone.now().astimezone(business_tz)
        today = now_in_business_tz.date()
        yesterday = today - timedelta(days=1)
        current_time = now_in_business_tz.time()

        # Personelin bugünkü veya dünkü (gece vardiyası ihtimaline karşı) vardiyalarını çek
        potential_shifts = ScheduledShift.objects.filter(
            staff=user,
            date__in=[today, yesterday]
        ).select_related('shift')
        
        for scheduled_shift in potential_shifts:
            shift_start_time = scheduled_shift.shift.start_time
            shift_end_time = scheduled_shift.shift.end_time

            # Durum 1: Normal (aynı gün biten) vardiya
            if shift_start_time <= shift_end_time:
                if scheduled_shift.date == today and shift_start_time <= current_time <= shift_end_time:
                    return True
            
            # Durum 2: Gece yarısını geçen (ertesi güne sarkan) vardiya
            else: # shift_start_time > shift_end_time
                # Vardiyanın başlangıç günündeysek
                if scheduled_shift.date == today and current_time >= shift_start_time:
                    return True
                # Vardiyanın bitiş günündeysek
                if scheduled_shift.date == yesterday and current_time <= shift_end_time:
                    return True

        # Hiçbir aktif vardiya bulunamadı
        return False