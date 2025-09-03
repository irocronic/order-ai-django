# templates/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryTemplateViewSet, MenuItemTemplateViewSet, VariantTemplateViewSet

router = DefaultRouter()
router.register(r'category-templates', CategoryTemplateViewSet, basename='categorytemplate')
router.register(r'menu-item-templates', MenuItemTemplateViewSet, basename='menuitemtemplate')
router.register(r'variant-templates', VariantTemplateViewSet, basename='varianttemplate')  # YENİ

urlpatterns = [
    path('', include(router.urls)),
]