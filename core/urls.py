from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static

# ViewSet'leri ve APIView'leri core.views'dan import ediyoruz
from core.views import (
    BusinessViewSet,
    TableViewSet,
    MenuItemViewSet,
    MenuItemVariantViewSet,
    OrderViewSet,
    PaymentViewSet,
    ReportView,
    DetailedSalesReportView,
    RegisterView,
    CategoryViewSet,
    OrderItemViewSet,
    WaitingCustomerList,
    WaitingCustomerDetail,
    StockViewSet,
    AccountSettingsView,
    GuestOrderCreateView,
    GuestMenuView,
    StockMovementViewSet,
    StaffUserViewSet,
    StaffPerformanceReportView,
    AdminUserManagementViewSet,
    KDSOrderViewSet,
    PasswordResetRequestView,
    PasswordResetCodeConfirmView,
    PagerViewSet,
    CampaignMenuViewSet,
    KDSScreenViewSet,
    ShiftViewSet,
    ScheduledShiftViewSet,
    NotificationSettingViewSet,
    # ================== YENİ IMPORT'LAR ==================
    IngredientViewSet,
    UnitOfMeasureViewSet,
    RecipeItemViewSet, # <<< HATA ÇÖZÜMÜ 1: RecipeItemViewSet'i import et
    # ================================================
)

from subscriptions.views import VerifyPurchaseView

# Genel API'ler için DefaultRouter
router = DefaultRouter()
router.register(r'businesses', BusinessViewSet, basename='business')
router.register(r'tables', TableViewSet, basename='table')
router.register(r'menu-items', MenuItemViewSet, basename='menuitem')
router.register(r'menu-item-variants', MenuItemVariantViewSet, basename='menuitemvariant')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'order_items', OrderItemViewSet, basename='orderitem')
router.register(r'stocks', StockViewSet, basename='stock')
router.register(r'stock-movements', StockMovementViewSet, basename='stockmovement')
router.register(r'ingredients', IngredientViewSet, basename='ingredient')
router.register(r'units-of-measure', UnitOfMeasureViewSet, basename='unitofmeasure')

# <<< HATA ÇÖZÜMÜ 2: Yeni RecipeItemViewSet'i router'a kaydet >>>
router.register(r'recipes', RecipeItemViewSet, basename='recipeitem')

router.register(r'staff-users', StaffUserViewSet, basename='staffuser')
router.register(r'pagers', PagerViewSet, basename='pager')
router.register(r'campaigns', CampaignMenuViewSet, basename='campaignmenu')
router.register(r'kds-screens', KDSScreenViewSet, basename='kdsscreen')
router.register(r'shifts', ShiftViewSet, basename='shift')
router.register(r'schedule', ScheduledShiftViewSet, basename='scheduledshift')

# YÖNETİCİ API'leri için ayrı bir DefaultRouter
admin_router = DefaultRouter()
admin_router.register(r'manage-users', AdminUserManagementViewSet, basename='admin-manage-user')
admin_router.register(r'notification-settings', NotificationSettingViewSet, basename='admin-notification-setting')


# URL'leri tanımla
urlpatterns = [
    # Router tarafından oluşturulan API URL'leri
    path('', include(router.urls)),
    path('admin-panel/', include(admin_router.urls)),


    # ==================== YENİ EKLENEN/GÜNCELLENEN BÖLÜM ====================
    # IngredientViewSet için özel action URL'leri
    path('ingredients/<int:pk>/adjust-stock/', IngredientViewSet.as_view({'post': 'adjust_stock'}), name='ingredient-adjust-stock'),
    path('ingredients/<int:pk>/history/', IngredientViewSet.as_view({'get': 'history'}), name='ingredient-history'),
    # =====================================================================


    # KDS Siparişleri için URL'ler
    re_path(r'^kds-orders/(?P<kds_slug>[-\w]+)/$', KDSOrderViewSet.as_view({'get': 'list'}), name='kdsorder-list'),
    re_path(r'^kds-orders/(?P<kds_slug>[-\w]+)/(?P<pk>\d+)/$', KDSOrderViewSet.as_view({'get': 'retrieve'}), name='kdsorder-detail'),
    re_path(r'^kds-orders/(?P<kds_slug>[-\w]+)/(?P<pk>\d+)/start-preparation/$', KDSOrderViewSet.as_view({'post': 'start_preparation'}), name='kdsorder-start-preparation'),
    re_path(r'^kds-orders/(?P<kds_slug>[-\w]+)/(?P<pk>\d+)/mark-ready-for-pickup/$', KDSOrderViewSet.as_view({'post': 'mark_ready_for_pickup'}), name='kdsorder-mark-ready'),
    
    # OrderItem için özel action URL'leri
    path('order_items/<int:pk>/start-preparing/', OrderItemViewSet.as_view({'post': 'start_preparing_item'}), name='orderitem-start-preparing'),
    path('order_items/<int:pk>/mark-ready/', OrderItemViewSet.as_view({'post': 'mark_item_ready'}), name='orderitem-mark-ready'),
    path('order_items/<int:pk>/mark-picked-up/', OrderItemViewSet.as_view({'post': 'mark_item_picked_up'}), name='orderitem-mark-picked-up'),

    # Raporlar
    path('reports/general/', ReportView.as_view(), name='report_general'),
    path('reports/detailed-sales/', DetailedSalesReportView.as_view(), name='detailed_sales_report'),
    path('reports/staff-performance/', StaffPerformanceReportView.as_view(), name='staff_performance_report'),
    
    # Kimlik Doğrulama ve Hesap Yönetimi
    path('register/', RegisterView.as_view(), name='register'),
    path('account/', AccountSettingsView.as_view(), name='account_settings'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm-code/', PasswordResetCodeConfirmView.as_view(), name='password_reset_code_confirm'),
    
    # Abonelik URL'si
    path('subscriptions/verify-purchase/', VerifyPurchaseView.as_view(), name='verify_purchase'),

    # Bekleyen Müşteri URL'leri
    path('waiting_customers/', WaitingCustomerList.as_view(), name='waiting_customer_list_create'),
    path('waiting_customers/<int:pk>/', WaitingCustomerDetail.as_view(), name='waiting_customer_detail'),

    # Misafir API'leri
    re_path(r'^guest/menu/(?P<table_uuid>[0-9a-f-]+)/$', GuestMenuView.as_view(), name='guest_menu_api'),
    re_path(r'^guest/orders/(?P<table_uuid>[0-9a-f-]+)/$', GuestOrderCreateView.as_view(), name='guest_order_create_api'),
]

# Geliştirme ortamında medya dosyalarını sunmak için
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)