# makarna_project/urls.py DOSYASININ DOĞRU VE TAM HALİ

from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import TokenRefreshView
from core.token import CustomTokenObtainPairView
from django.http import HttpResponse

# --- EKLENMESİ GEREKEN IMPORT SATIRI ---
from core.views.public_views import public_business_site_view

# --- BU İMPORTLAR ZATEN VARDI, KONTROL EDİN ---
from core.views import (
    guest_table_view,
    guest_takeaway_view,
    GuestTakeawayOrderUpdateView
)
from django.conf import settings
from django.conf.urls.static import static

# Basit bir root view tanımı
def root_view(request):
    return HttpResponse(
        "Merhaba, bu Django projesidir! Ana dizine başarıyla ulaştınız."
    )

urlpatterns = [
    path('', root_view, name='root'),
    path('admin/', admin.site.urls),

    # --- EKLENMESİ GEREKEN WEB SİTESİ URL SATIRI ---
    path('site/<slug:slug>/', public_business_site_view, name='public_business_site'),
    # --- / EKLENMESİ GEREKEN SATIR SONU ---

    path('api/templates/', include('templates.urls')),
    path('api/', include('core.urls')), # API URL'leri

    # Misafir Kullanıcı URL'leri (Bunlar zaten vardı)
    re_path(r'^guest/tables/(?P<table_uuid>[0-9a-f-]+)/$', guest_table_view, name='guest_table_view'),
    re_path(r'^guest/takeaway/(?P<order_uuid>[0-9a-f-]+)/$', guest_takeaway_view, name='guest_takeaway_view'),
    re_path(r'^guest/takeaway/(?P<order_uuid>[0-9a-f-]+)/add-item/$', GuestTakeawayOrderUpdateView.as_view(), name='guest_takeaway_order_update_api'),

    # JWT Kimlik Doğrulama URL'leri
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Abonelik URL'leri
    path('api/subscriptions/', include('subscriptions.urls')),
]

# Geliştirme ortamında medya dosyalarını sunmak için
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)