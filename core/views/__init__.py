# core/views/__init__.py

from .auth_views import (
    RegisterView,
    PasswordResetRequestView,
    PasswordResetCodeConfirmView,
)
from .business_views import BusinessViewSet, BusinessLayoutViewSet, LayoutElementViewSet
from .menu_views import CategoryViewSet, MenuItemViewSet, MenuItemVariantViewSet
from .order_views import OrderViewSet, OrderItemViewSet
# GÜNCELLEME 1: payment_provider_webhook buraya import edildi
from .payment_views import PaymentViewSet, payment_provider_webhook 
from .report_views import ReportView, DetailedSalesReportView
from .stock_views import (
    IngredientViewSet, 
    UnitOfMeasureViewSet, 
    RecipeItemViewSet,
    SupplierViewSet,
    PurchaseOrderViewSet,
)
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
from .business_website_views import (
    BusinessWebsiteDetailView,
    business_public_website_api,
    business_website_preview_api,
    business_website_view,
)
from .reservation_views import (
    ReservationViewSet,
    PublicReservationCreateView,
    TableAvailabilityAPIView, # TableAvailabilityAPIView de eksikti, eklendi
)

__all__ = [
    'RegisterView',
    'PasswordResetRequestView',
    'PasswordResetCodeConfirmView',
    'BusinessViewSet',
    'BusinessLayoutViewSet',
    'LayoutElementViewSet',
    'CategoryViewSet',
    'MenuItemViewSet',
    'MenuItemVariantViewSet',
    'OrderViewSet',
    'OrderItemViewSet',
    'PaymentViewSet',
    'ReportView',
    'DetailedSalesReportView',
    'StaffPerformanceReportView',
    'IngredientViewSet',
    'UnitOfMeasureViewSet',
    'RecipeItemViewSet',
    'SupplierViewSet',
    'PurchaseOrderViewSet',
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
    'BusinessWebsiteDetailView',
    'business_public_website_api',
    'business_website_preview_api',
    'business_website_view',
    'ReservationViewSet',
    'PublicReservationCreateView',
    'TableAvailabilityAPIView', # Eksik olan import __all__ listesine de eklendi
    # GÜNCELLEME 2: Yeni fonksiyon __all__ listesine eklendi
    'payment_provider_webhook', 
]