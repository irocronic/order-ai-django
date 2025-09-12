# makarna_project/urls.py DOSYASININ GÜNCELLENMİŞ VE EKSİKSİZ HALİ

from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import TokenRefreshView
from core.token import CustomTokenObtainPairView
from django.http import HttpResponse

# --- EKLENMESİ GEREKEN IMPORT SATIRI ---
# Bu satır, herkese açık site görünümünü (view) projenin ana URL'lerine tanıtır.
from core.views.public_views import public_business_site_view

# Bu importlar daha önceki dosyalarda vardı ve gereklidir.
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

    # --- 404 HATASININ ÇÖZÜMÜ OLAN EKSİK SATIR BURASI ---
    # '/site/' ile başlayan bir link geldiğinde hangi view'in çalışacağını belirtir.
    path('site/<slug:slug>/', public_business_site_view, name='public_business_site'),
    # --- / EKSİK SATIR SONU ---

    # API ve diğer URL'leriniz
    path('api/templates/', include('templates.urls')),
    path('api/', include('core.urls')), # /api/ ile başlayan tüm istekler core/urls.py'ye yönlendirilir.

    # Misafir Kullanıcı URL'leri
    re_path(r'^guest/tables/(?P<table_uuid>[0-9a-f-]+)/$', guest_table_view, name='guest_table_view'),
    re_path(r'^guest/takeaway/(?P<order_uuid>[0-9a-f-]+)/$', guest_takeaway_view, name='guest_takeaway_view'),
    re_path(r'^guest/takeaway/(?P<order_uuid>[0-9a-f-]+)/add-item/$', GuestTakeawayOrderUpdateView.as_view(), name='guest_takeaway_order_update_api'),

    # JWT Kimlik Doğrulama URL'leri
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Abonelik URL'leri
    path('api/subscriptions/', include('subscriptions.urls')),
]

# Geliştirme ortamında (DEBUG=True) medya dosyalarını sunmak için gereklidir.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)