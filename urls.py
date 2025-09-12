# makarna_project/urls.py

from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import TokenRefreshView
from core.token import CustomTokenObtainPairView
from django.http import HttpResponse
from django.conf import settings

# --- EKLENMESİ GEREKEN IMPORT SATIRI ---
from core.views.public_views import public_business_site_view

# Bu importlar daha önceki dosyalarda vardı ve gereklidir.
from core.views import (
    guest_table_view,
    guest_takeaway_view,
    GuestTakeawayOrderUpdateView
)
from django.conf.urls.static import static

# Basit bir root view tanımı
def root_view(request):
    return HttpResponse(
        "Merhaba, bu Django projesidir! Ana dizine başarıyla ulaştınız."
    )

# === DEBUG FUNCTION ===
def debug_urls_view(request):
    from django.urls import get_resolver
    resolver = get_resolver()
    url_list = []
    for pattern in resolver.url_patterns:
        url_list.append(f"- {pattern}")
    return HttpResponse(f"<h2>Mevcut URL'ler:</h2><br>{'<br>'.join(url_list)}")

def debug_businesses_view(request):
    from core.models import Business
    businesses = Business.objects.all()
    business_list = []
    for biz in businesses:
        business_list.append(f"- ID: {biz.id}, Name: '{biz.name}', Slug: '{biz.website_slug}', Owner: '{biz.owner.username}', Owner Active: {biz.owner.is_active}")
    return HttpResponse(f"<h2>Mevcut İşletmeler ({businesses.count()}):</h2><br>{'<br>'.join(business_list)}")

urlpatterns = [
    path('', root_view, name='root'),
    path('admin/', admin.site.urls),

    # === 404 HATASININ ÇÖZÜMÜ OLAN EKSİK SATIR BURASI ===
    path('site/<slug:slug>/', public_business_site_view, name='public_business_site'),
    # === / EKSİK SATIR SONU ===

    # === DEBUG URL'LERİ ===
    path('debug-urls/', debug_urls_view, name='debug_urls'),
    path('debug-businesses/', debug_businesses_view, name='debug_businesses'),

    # API ve diğer URL'leriniz
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