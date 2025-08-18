# subscriptions/admin.py

from django.contrib import admin
from .models import Plan, Subscription

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_tables', 'max_staff', 'max_kds_screens', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name',)
    fieldsets = (
        ('Genel Bilgiler', {
            'fields': ('name', 'is_active')
        }),
        ('Uygulama Mağazası Ürün IDleri', {
            'fields': ('google_product_id_monthly', 'google_product_id_yearly', 'apple_product_id_monthly', 'apple_product_id_yearly')
        }),
        ('Plan Limitleri', {
            'fields': ('max_tables', 'max_staff', 'max_kds_screens', 'max_categories', 'max_menu_items', 'max_variants')
        }),
    )

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('business', 'plan', 'status', 'expires_at', 'provider')
    list_filter = ('status', 'plan', 'provider')
    search_fields = ('business__name', 'business__owner__username')
    list_select_related = ('business', 'plan')
    autocomplete_fields = ('business', 'plan')
    readonly_fields = ('created_at', 'updated_at')