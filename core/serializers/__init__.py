# core/serializers/__init__.py

from .user_serializers import (
    RegisterSerializer,
    AccountSettingsSerializer,
    StaffUserSerializer,
    StaffPermissionUpdateSerializer,
    StaffNotificationPermissionUpdateSerializer,
    PasswordResetRequestSerializer,
    PasswordResetCodeConfirmSerializer,
)
# === GÜNCELLEME BURADA ===
from .business_serializers import (
    BusinessSerializer,
    TableSerializer,
    BusinessLayoutSerializer,
    LayoutElementSerializer,
    BusinessPaymentSettingsSerializer, # <-- BU SATIRI EKLEYİN
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
    IngredientSerializer, 
    UnitOfMeasureSerializer,
    RecipeItemSerializer,
    IngredientStockMovementSerializer,
    SupplierSerializer,
    PurchaseOrderItemSerializer,
    PurchaseOrderSerializer,
)
from .report_serializers import (
    StaffPerformanceSerializer,
    DetailedSaleItemSerializer,
)
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
from .reservation_serializers import (
    ReservationSerializer,
    PublicReservationCreateSerializer,
)
from .business_website_serializers import (
    BusinessWebsiteSerializer,
    BusinessWebsiteUpdateSerializer,
    BusinessPublicSerializer,
)

__all__ = [
    'RegisterSerializer',
    'AccountSettingsSerializer',
    'StaffUserSerializer',
    'StaffPermissionUpdateSerializer',
    'StaffNotificationPermissionUpdateSerializer',
    'PasswordResetRequestSerializer',
    'PasswordResetCodeConfirmSerializer',
    'BusinessSerializer',
    'TableSerializer',
    'BusinessLayoutSerializer',
    'LayoutElementSerializer',
    'BusinessPaymentSettingsSerializer', # <-- BU SATIRI EKLEYİN
    'CategorySerializer',
    'MenuItemVariantSerializer',
    'MenuItemSerializer',
    'IngredientSerializer', 
    'UnitOfMeasureSerializer',
    'RecipeItemSerializer',
    'IngredientStockMovementSerializer',
    'SupplierSerializer',
    'PurchaseOrderItemSerializer',
    'PurchaseOrderSerializer',
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
    'ReservationSerializer',
    'PublicReservationCreateSerializer',
    'BusinessWebsiteSerializer',
    'BusinessWebsiteUpdateSerializer',
    'BusinessPublicSerializer',
]