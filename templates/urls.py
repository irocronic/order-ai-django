# templates/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryTemplateViewSet, MenuItemTemplateViewSet # MenuItemTemplateViewSet import edildi

router = DefaultRouter()
router.register(r'category-templates', CategoryTemplateViewSet, basename='categorytemplate')
# === YENİ SATIR ===
router.register(r'menu-item-templates', MenuItemTemplateViewSet, basename='menuitemtemplate')

urlpatterns = [
    path('', include(router.urls)),
]