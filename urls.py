# makarna_project/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from core.token import CustomTokenObtainPairView  # Custom token view
from django.http import HttpResponse

# Basit root view; isteğe göre düzenlenebilir.
def root_view(request):
    return HttpResponse("Merhaba, bu Django projesidir!")

urlpatterns = [
    path('', root_view, name='root'),
    path('admin/', admin.site.urls),
    
    # Mevcut API URL'leriniz
    path('api/', include('core.urls')),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # === YENİ: Bu satırı ana urls.py'ye ekleyin ===
    # /api/subscriptions/ ile başlayan tüm istekleri 'subscriptions' uygulamasına yönlendirir.
    path('api/subscriptions/', include('subscriptions.urls')),
    # === /YENİ ===
]