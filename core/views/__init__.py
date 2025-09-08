# core/views/__init__.py

from .auth_views import (
    RegisterView,
    PasswordResetRequestView,
    PasswordResetCodeConfirmView,
)
from .business_views import BusinessViewSet
from .menu_views import CategoryViewSet, MenuItemViewSet, MenuItemVariantViewSet
from .order_views import OrderViewSet, OrderItemViewSet
from .payment_views import PaymentViewSet
from .report_views import ReportView, DetailedSalesReportView
# === GÜNCELLEME BURADA BAŞLIYOR ===
from .stock_views import (
    StockViewSet, 
    StockMovementViewSet, 
    IngredientViewSet, 
    UnitOfMeasureViewSet, 
    RecipeItemViewSet,
    # YENİ: Alım Yönetimi ViewSet'leri eklendi
    SupplierViewSet,
    PurchaseOrderViewSet,
)
# === GÜNCELLEME BURADA BİTİYOR ===
from .table_views import TableViewSet
from .waiting_customer_views import WaitingCustomerList, WaitingCustomerDetail
from .user_views import AccountSettingsView, StaffUserViewSet
from .guest_views import guest_table_view, guest_takeaway_view
from .guest_api_views import (
    GuestOrderCreateView,
    GuestMenuView,
    GuestTakeawayMenuView,
    GuestTakeawayOrderUpdateView
)
from .staff_report_views import StaffPerformanceReportView
from .admin_views import AdminUserManagementViewSet, NotificationSettingViewSet
from .kds_views import KDSOrderViewSet
from .pager_views import PagerViewSet
from .campaign_views import CampaignMenuViewSet
from .kds_management_views import KDSScreenViewSet
from .schedule_views import ShiftViewSet, ScheduledShiftViewSet

__all__ = [
    'RegisterView',
    'PasswordResetRequestView',
    'PasswordResetCodeConfirmView',
    'BusinessViewSet',
    'CategoryViewSet',
    'MenuItemViewSet',
    'MenuItemVariantViewSet',
    'OrderViewSet',
    'OrderItemViewSet',
    'PaymentViewSet',
    'ReportView',
    'DetailedSalesReportView',
    'StaffPerformanceReportView',
    'StockViewSet',
    'StockMovementViewSet',
    'IngredientViewSet',
    'UnitOfMeasureViewSet',
    'RecipeItemViewSet',
    # === YENİ: Alım Yönetimi ViewSet'leri __all__ listesine eklendi ===
    'SupplierViewSet',
    'PurchaseOrderViewSet',
    # ===============================================================
    'TableViewSet',
    'WaitingCustomerList',
    'WaitingCustomerDetail',
    'AccountSettingsView',
    'StaffUserViewSet',
    'guest_table_view',
    'guest_takeaway_view',
    'GuestOrderCreateView',
    'GuestMenuView',
    'GuestTakeawayMenuView',
    'GuestTakeawayOrderUpdateView',
    'AdminUserManagementViewSet',
    'NotificationSettingViewSet',
    'KDSOrderViewSet',
    'PagerViewSet',
    'CampaignMenuViewSet',
    'KDSScreenViewSet',
    'ShiftViewSet',
    'ScheduledShiftViewSet',
]