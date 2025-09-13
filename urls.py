from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import TokenRefreshView
from core.token import CustomTokenObtainPairView

# Gerekli view fonksiyonlarını 'core' uygulamasından import ediyoruz
from core.views import (
    guest_table_view,
    guest_takeaway_view,
    GuestTakeawayOrderUpdateView,
    business_website_view # <-- Web sitesini gösterecek fonksiyon
)

# Projenin ana (root) adresi için basit bir karşılama mesajı
def root_view(request):
    return HttpResponse(
        "Merhaba, bu OrderAI Django projesidir! Ana dizine başarıyla ulaştınız."
    )

urlpatterns = [
    # Ana Sayfa ve Admin Paneli
    path('', root_view, name='root'),
    path('admin/', admin.site.urls),

    # === İŞLETME WEB SİTESİ URL'İ DOĞRU YERDE ===
    # Kullanıcıların göreceği web sitesi linki (örn: /website/isletme-adi/)
    # Bu linkin /api/ altında olmaması gerekir.
    path('website/<slug:business_slug>/', business_website_view, name='business-website'),
    # ===============================================

    # API ile ilgili tüm linkler /api/ ön ekiyle başlar
    path('api/templates/', include('templates.urls')),
    path('api/subscriptions/', include('subscriptions.urls')),
    path('api/', include('core.urls')), # Diğer tüm API URL'leri

    # Misafir Kullanıcılar için URL'ler
    re_path(r'^guest/tables/(?P<table_uuid>[0-9a-f-]+)/$', guest_table_view, name='guest_table_view'),
    re_path(r'^guest/takeaway/(?P<order_uuid>[0-9a-f-]+)/$', guest_takeaway_view, name='guest_takeaway_view'),
    re_path(r'^guest/takeaway/(?P<order_uuid>[0-9a-f-]+)/add-item/$', GuestTakeawayOrderUpdateView.as_view(), name='guest_takeaway_order_update_api'),

    # JWT Kimlik Doğrulama URL'leri
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

# Geliştirme ortamında medya dosyalarını sunmak için
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)