# core/utils/order_helpers.py

from rest_framework.exceptions import PermissionDenied
from ..models import Business, CustomUser as User

class PermissionKeys:
    VIEW_REPORTS = 'view_reports'
    MANAGE_CREDIT_SALES = 'manage_credit_sales'
    MANAGE_MENU = 'manage_menu'
    MANAGE_STOCK = 'manage_stock'
    MANAGE_TABLES = 'manage_tables'
    VIEW_COMPLETED_ORDERS = 'view_completed_orders'
    VIEW_PENDING_ORDERS = 'view_pending_orders' # Django modellerinde de bu anahtar kullanılmalı
    TAKE_ORDERS = 'take_orders'
    MANAGE_STAFF = 'manage_staff'
    MANAGE_WAITING_CUSTOMERS = 'manage_waiting_customers'
    VIEW_ACCOUNT_SETTINGS = 'view_account_settings'
    MANAGE_KDS = 'manage_kds' # <<< --- EKLENDİ ---

def get_user_business(user: User):
    if not user or not user.is_authenticated:
        return None
    if user.user_type == 'business_owner':
        try:
            return user.owned_business
        except Business.DoesNotExist:
            raise PermissionDenied("İşletme sahibi olarak bir işletmeniz bulunmuyor veya işletmeniz silinmiş.")
        except AttributeError: # owned_business attr'si yoksa (örn: user objesi tam değilse)
            raise PermissionDenied("İşletme sahibi bilgileri eksik veya ilgili işletme bulunamadı.")
    elif user.user_type == 'staff' or user.user_type == 'kitchen_staff': # kitchen_staff da eklendi
        if not user.associated_business:
            raise PermissionDenied("Bir işletmeye atanmamışsınız. Yöneticinizle iletişime geçin.")
        return user.associated_business
    return None