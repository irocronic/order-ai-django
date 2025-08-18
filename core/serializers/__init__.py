# core/serializers/__init__.py

from .user_serializers import (
    RegisterSerializer,
    AccountSettingsSerializer,
    StaffUserSerializer,
    StaffPermissionUpdateSerializer,
    StaffNotificationPermissionUpdateSerializer,
    BusinessForAdminSerializer,
    AdminBusinessOwnerSerializer,
    AdminStaffUserSerializer,
    UserActivationSerializer,
    AdminUserNotificationPermissionUpdateSerializer,
    PasswordResetRequestSerializer,
    PasswordResetCodeConfirmSerializer,
)
from .business_serializers import (
    BusinessSerializer,
    TableSerializer,
)
from .menu_serializers import (
    CategorySerializer,
    MenuItemVariantSerializer,
    MenuItemSerializer,
)
from .payment_serializers import (
    PaymentSerializer,
    CreditPaymentDetailsSerializer,
)
from .order_serializers import (
    OrderItemExtraSerializer,
    GuestOrderItemSerializer,
    OrderItemSerializer,
    OrderTableUserSerializer,
    OrderSerializer,
    GuestOrderCreateSerializer,
    KDSOrderItemSerializer,
    KDSOrderSerializer,
    SimplePagerInfoSerializer,
)
from .waiting_customer_serializers import (
    WaitingCustomerSerializer,
)
from .stock_serializers import (
    StockSerializer,
    StockMovementSerializer,
)
# ==================== YENİ EKLENEN BÖLÜM (IMPORT) ====================
from .report_serializers import (
    StaffPerformanceSerializer,
    DetailedSaleItemSerializer, # YENİ: Bu satır eklendi
)
# =====================================================================
from .pager_serializers import (
    PagerSerializer,
    PagerOrderSerializer,
)
from .campaign_serializers import (
    CampaignMenuSerializer,
    CampaignMenuItemSerializer,
)
from .kds_serializers import (
    KDSScreenSerializer,
)
from .schedule_serializers import (
    ShiftSerializer,
    ScheduledShiftSerializer,
)


__all__ = [
    'RegisterSerializer',
    'AccountSettingsSerializer',
    'StaffUserSerializer',
    'StaffPermissionUpdateSerializer',
    'StaffNotificationPermissionUpdateSerializer',
    'BusinessForAdminSerializer',
    'AdminBusinessOwnerSerializer',
    'AdminStaffUserSerializer',
    'UserActivationSerializer',
    'AdminUserNotificationPermissionUpdateSerializer',
    'PasswordResetRequestSerializer',
    'PasswordResetCodeConfirmSerializer',
    'BusinessSerializer',
    'TableSerializer',
    'CategorySerializer',
    'MenuItemVariantSerializer',
    'MenuItemSerializer',
    'StockSerializer',
    'StockMovementSerializer',
    'PaymentSerializer',
    'CreditPaymentDetailsSerializer',
    'OrderItemExtraSerializer',
    'GuestOrderItemSerializer',
    'OrderItemSerializer',
    'OrderTableUserSerializer',
    'OrderSerializer',
    'GuestOrderCreateSerializer',
    'KDSOrderItemSerializer',
    'KDSOrderSerializer',
    'SimplePagerInfoSerializer',
    'WaitingCustomerSerializer',
    'StaffPerformanceSerializer',
    'DetailedSaleItemSerializer',
    'PagerSerializer',
    'PagerOrderSerializer',
    'CampaignMenuSerializer',
    'CampaignMenuItemSerializer',
    'KDSScreenSerializer',
    'ShiftSerializer',
    'ScheduledShiftSerializer',
]