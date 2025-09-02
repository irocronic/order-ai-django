# templates/admin.py

from django.contrib import admin
from .models import CategoryTemplate

@admin.register(CategoryTemplate)
class CategoryTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'language', 'icon_name')
    list_filter = ('language',)
    search_fields = ('name',)