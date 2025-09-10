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
# ================== GÜNCELLEME BURADA ==================
from .stock_serializers import (
    # --- SİLİNDİ ---
    IngredientSerializer, 
    UnitOfMeasureSerializer,
    RecipeItemSerializer,
    IngredientStockMovementSerializer,
    # === YENİ: Alım Yönetimi Serializer'ları eklendi ===
    SupplierSerializer,
    PurchaseOrderItemSerializer,
    PurchaseOrderSerializer,
    # =================================================
)
# =======================================================
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
    'CategorySerializer',
    'MenuItemVariantSerializer',
    'MenuItemSerializer',
    # ================== GÜNCELLEME BURADA ==================
    # --- SİLİNDİ ---
    'IngredientSerializer', 
    'UnitOfMeasureSerializer',
    'RecipeItemSerializer',
    'IngredientStockMovementSerializer',
    # === YENİ: Alım Yönetimi Serializer'ları __all__ listesine eklendi ===
    'SupplierSerializer',
    'PurchaseOrderItemSerializer',
    'PurchaseOrderSerializer',
    # ===================================================================
    # =======================================================
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