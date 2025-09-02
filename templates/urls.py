# templates/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryTemplateViewSet

router = DefaultRouter()
router.register(r'category-templates', CategoryTemplateViewSet, basename='categorytemplate')

urlpatterns = [
    path('', include(router.urls)),
]