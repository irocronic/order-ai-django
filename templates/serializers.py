# templates/serializers.py

from rest_framework import serializers
from .models import CategoryTemplate

class CategoryTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryTemplate
        fields = ['id', 'name', 'icon_name', 'language']