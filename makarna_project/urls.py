# makarna_project/urls.py

from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import TokenRefreshView
from core.token import CustomTokenObtainPairView

# --- GÜNCELLENMİŞ IMPORT SATIRI ---
# Artık API view yerine Django template view'larını import ediyoruz.
from core.views import (
    guest_table_view,
    guest_takeaway_view, # API view'ı yerine bu fonksiyonu kullanacağız.
    GuestTakeawayOrderUpdateView # Bu API view'ı ürün ekleme için hala gerekli.
)
# --- GÜNCELLEME SONU ---

from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

# Basit bir root view tanımı
def root_view(request):
    return HttpResponse(
        "Merhaba, bu Django projesidir! Ana dizine başarıyla ulaştınız."
    )

urlpatterns = [
    path('', root_view, name='root'),

    path('admin/', admin.site.urls),
    path('api/templates/', include('templates.urls')),
    path('api/', include('core.urls')), # API URL'leri

    # --- MİSAFİR KULLANICILAR İÇİN URL'LER ---
    # Mevcut Masa Siparişi URL'si (Django Template View)
    re_path(r'^guest/tables/(?P<table_uuid>[0-9a-f-]+)/$', guest_table_view, name='guest_table_view'),
    
    # YENİ EKLENEN URL'LER: Takeaway Misafir Siparişi için
    
    # 1. Takeaway siparişi için menüyü gösteren WEB SAYFASI URL'si
    # DÜZELTME: API View yerine Django Template View'ı çağırıyoruz.
    re_path(r'^guest/takeaway/(?P<order_uuid>[0-9a-f-]+)/$', guest_takeaway_view, name='guest_takeaway_view'),
    
    # 2. Misafirin, takeaway siparişine ürün eklemesini sağlayan API endpoint'i (BU AYNI KALIYOR)
    re_path(r'^guest/takeaway/(?P<order_uuid>[0-9a-f-]+)/add-item/$', GuestTakeawayOrderUpdateView.as_view(), name='guest_takeaway_order_update_api'),
    # --- YENİ URL'LER SONU ---

    # JWT Kimlik Doğrulama URL'leri
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

# Geliştirme ortamında medya dosyalarını sunmak için
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)