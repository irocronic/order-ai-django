# makarna_project/urls.py (manage.py ile aynı dizindeki)

from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import TokenRefreshView
from core.token import CustomTokenObtainPairView
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

# Gerekli view fonksiyonlarını import ediyoruz
from core.views import (
    guest_table_view,
    guest_takeaway_view,
    GuestTakeawayOrderUpdateView,
    business_website_view # Web sitesi view'ı
)

def root_view(request):
    return HttpResponse(
        "Merhaba, bu OrderAI Django projesidir! Ana dizine başarıyla ulaştınız."
    )

urlpatterns = [
    # Ana Sayfa ve Admin
    path('', root_view, name='root'),
    path('admin/', admin.site.urls),

    # === ÖNEMLİ: İşletme Web Sitesi URL'i ===
    path('website/<slug:business_slug>/', business_website_view, name='business-website'),
    # =====================================

    # API ve diğer URL'ler
    path('api/', include('core.urls')),
    path('api/templates/', include('templates.urls')),
    path('api/subscriptions/', include('subscriptions.urls')),

    # Misafir Kullanıcı URL'leri
    re_path(r'^guest/tables/(?P<table_uuid>[0-9a-f-]+)/$', guest_table_view, name='guest_table_view'),
    re_path(r'^guest/takeaway/(?P<order_uuid>[0-9a-f-]+)/$', guest_takeaway_view, name='guest_takeaway_view'),
    re_path(r'^guest/takeaway/(?P<order_uuid>[0-9a-f-]+)/add-item/$', GuestTakeawayOrderUpdateView.as_view(), name='guest_takeaway_order_update_api'),

    # JWT Auth
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)