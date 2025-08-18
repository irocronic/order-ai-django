# subscriptions/urls.py (YENİ DOSYA)
from django.urls import path
from .views import VerifyPurchaseView

urlpatterns = [
    path('verify-purchase/', VerifyPurchaseView.as_view(), name='verify-purchase'),
]

# projenizin ana urls.py dosyasına ekleyin:
# from django.urls import path, include
# urlpatterns = [
#     ...
#     path('api/subscriptions/', include('subscriptions.urls')),
#     ...
# ]