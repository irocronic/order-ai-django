# templates/serializers.py

from rest_framework import serializers
from .models import CategoryTemplate, MenuItemTemplate # MenuItemTemplate import edildi

class CategoryTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryTemplate
        fields = ['id', 'name', 'icon_name', 'language']

# === YENİ SERIALIZER BAŞLANGICI ===
class MenuItemTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemTemplate
        fields = ['id', 'name', 'language', 'category_template']
# === YENİ SERIALIZER SONU ===