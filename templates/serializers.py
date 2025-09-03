# templates/serializers.py

from rest_framework import serializers
from .models import CategoryTemplate, MenuItemTemplate, VariantTemplate

class CategoryTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryTemplate
        fields = ['id', 'name', 'icon_name', 'language']

class MenuItemTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemTemplate
        fields = ['id', 'name', 'language', 'category_template']

# === YENİ SERIALIZER ===
class VariantTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariantTemplate
        fields = ['id', 'name', 'price_multiplier', 'icon_name', 'language', 'display_order']