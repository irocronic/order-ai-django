# core/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.db import models

# --- YENİ: Subscription modeli buraya import edildi ---
from subscriptions.models import Subscription

from .models import (
    Business, Table, MenuItem, Order, OrderItem, Payment, Category,
    MenuItemVariant, Stock, WaitingCustomer, CreditPaymentDetails,
    StockMovement, CustomUser, OrderTableUser, OrderItemExtra,
    Pager, CampaignMenu, CampaignMenuItem,
    KDSScreen,
    Shift, ScheduledShift,
    STAFF_PERMISSION_CHOICES, NOTIFICATION_EVENT_TYPES,
    # === YENİ: UnitOfMeasure ve Ingredient modelleri import edildi ===
    UnitOfMeasure, Ingredient, RecipeItem, IngredientStockMovement,
    Supplier, PurchaseOrder, PurchaseOrderItem # YENİ EKLENENLER
    # =============================================================
)

# === YENİ: UnitOfMeasure için Admin sınıfı eklendi ===
@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbreviation')
    search_fields = ('name',)
# =====================================================

# === YENİ: Supplier, PurchaseOrder için Admin sınıfları ===
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'contact_person', 'email', 'phone')
    list_filter = ('business',)
    search_fields = ('name', 'contact_person', 'email', 'business__name')

class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
    autocomplete_fields = ['ingredient']

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'business', 'order_date', 'status', 'total_amount')
    list_filter = ('status', 'business', 'supplier')
    search_fields = ('id', 'supplier__name', 'business__name')
    list_editable = ('status',)
    inlines = [PurchaseOrderItemInline]
    autocomplete_fields = ['supplier']
# ==========================================================

# === GÜNCELLENECEK: IngredientAdmin ===
@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'stock_quantity', 'unit', 'supplier', 'cost_price', 'alert_threshold')
    list_filter = ('business', 'unit', 'supplier')
    search_fields = ('name', 'business__name', 'supplier__name')
    autocomplete_fields = ['business', 'unit', 'supplier']
    list_editable = ('stock_quantity', 'cost_price', 'alert_threshold')
# ======================================

# === YENİ: RecipeItem için Admin sınıfı ===
@admin.register(RecipeItem)
class RecipeItemAdmin(admin.ModelAdmin):
    list_display = ('variant', 'ingredient', 'quantity', 'ingredient_unit')
    list_filter = ('variant__menu_item__business', 'ingredient__business')
    search_fields = ('variant__name', 'variant__menu_item__name', 'ingredient__name')
    autocomplete_fields = ['variant', 'ingredient']
    
    def ingredient_unit(self, obj):
        return obj.ingredient.unit.abbreviation
    ingredient_unit.short_description = 'Birim'
# =============================================

# === YENİ: IngredientStockMovement için Admin sınıfı ===
@admin.register(IngredientStockMovement)
class IngredientStockMovementAdmin(admin.ModelAdmin):
    list_display = ('ingredient', 'movement_type', 'quantity_change', 'quantity_before', 'quantity_after', 'timestamp', 'user')
    list_filter = ('movement_type', 'ingredient__business', 'timestamp')
    search_fields = ('ingredient__name', 'user__username', 'description')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    list_select_related = ('ingredient', 'user', 'related_order_item')
# =======================================================

# CustomUserAdmin sınıfında değişiklik yok, aynı kalıyor
@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type',
                    'associated_business', 'is_staff', 'is_active', 'is_approved_by_admin')
    list_filter = BaseUserAdmin.list_filter + ('user_type', 'associated_business', 'is_active', 'is_approved_by_admin')
    search_fields = BaseUserAdmin.search_fields + ('associated_business__name',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions & Type', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser', 
                'is_approved_by_admin',
                'user_type',
                'groups', 'user_permissions'
            )
        }),
        ('Business, Staff, KDS & Notification Info', {
            'fields': ('associated_business', 'staff_permissions', 'notification_permissions', 'accessible_kds_screens')
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {
            'classes': ('wide',),
            'fields': ('user_type', 'associated_business', 'staff_permissions', 'notification_permissions', 'accessible_kds_screens',
                       'first_name', 'last_name', 'email', 
                       'is_active', 'is_approved_by_admin'),
        }),
    )
    filter_horizontal = BaseUserAdmin.filter_horizontal + ('accessible_kds_screens',)
    
    actions = ['approve_selected_users', 'deactivate_selected_users', 'activate_selected_users']

    def approve_selected_users(self, request, queryset):
        updated_count = queryset.filter(
            is_approved_by_admin=False, 
            user_type__in=['customer', 'business_owner']
        ).update(is_active=True, is_approved_by_admin=True)
        self.message_user(request, f"{updated_count} kullanıcı başarıyla onaylandı ve aktifleştirildi.")
    approve_selected_users.short_description = "Seçili kullanıcıları onayla ve aktifleştir"

    def deactivate_selected_users(self, request, queryset):
        updated_count = queryset.update(is_active=False)
        self.message_user(request, f"{updated_count} kullanıcı başarıyla pasifleştirildi.")
    deactivate_selected_users.short_description = "Seçili kullanıcıları pasifleştir"

    def activate_selected_users(self, request, queryset):
        updated_count = queryset.filter(is_approved_by_admin=True).update(is_active=True)
        self.message_user(request, f"{updated_count} onaylı kullanıcı başarıyla aktifleştirildi.")
    activate_selected_users.short_description = "Seçili (onaylı) kullanıcıları aktifleştir"

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "accessible_kds_screens":
            obj_id = request.resolver_match.kwargs.get('object_id')
            if obj_id:
                user_instance = self.get_object(request, object_id=obj_id)
                if user_instance:
                    target_business = user_instance.associated_business or getattr(user_instance, 'owned_business', None)
                    if target_business:
                        kwargs["queryset"] = KDSScreen.objects.filter(business=target_business)
                    else:
                        kwargs["queryset"] = KDSScreen.objects.none()
        return super().formfield_for_manytomany(db_field, request, **kwargs)


# --- YENİ: Subscription modelini Business admin içinde yönetmek için bir inline oluşturuyoruz ---
class SubscriptionInline(admin.StackedInline):
    model = Subscription
    can_delete = False
    verbose_name_plural = 'Abonelik Bilgileri'
    # Gösterilecek ve düzenlenecek alanlar
    fields = ('plan', 'status', 'expires_at', 'provider', 'provider_subscription_id')
    autocomplete_fields = ('plan',)
    readonly_fields = ('provider', 'provider_subscription_id',)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    # GÜNCELLENDİ: list_display, yeni metotları kullanacak şekilde değiştirildi.
    list_display = ('name', 'owner_username', 'is_setup_complete', 'get_subscription_status', 'get_subscription_expires_at')
    
    search_fields = ('name', 'owner__username')
    
    # GÜNCELLEME: list_filter, yeni ilişki üzerinden sorgu yapacak şekilde değiştirildi.
    list_filter = ('owner','is_setup_complete', 'subscription__status', 'subscription__plan')
    
    # GÜNCELLEME: İlişkili model alanları 'list_editable' içinde kullanılamaz.
    list_editable = ('is_setup_complete',)
    
    # YENİ: Oluşturduğumuz SubscriptionInline'ı buraya ekliyoruz.
    inlines = [SubscriptionInline]
    
    readonly_fields = ('owner',)
    
    # GÜNCELLENDİ: fieldsets içindeki abonelik alanları artık inline'da yönetildiği için kaldırıldı.
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('name', 'owner', 'address', 'phone')
        }),
        ('Uygulama Ayarları', {
            'fields': ('is_setup_complete', 'currency_code', 'timezone')
        }),
    )

    # Sorgu optimizasyonu için eklendi
    list_select_related = ('owner', 'subscription', 'subscription__plan') 

    def owner_username(self, obj):
        return obj.owner.username
    owner_username.short_description = 'Sahip (Kullanıcı Adı)'
    
    # YENİ: Abonelik durumunu göstermek için metot
    @admin.display(description='Abonelik Durumu', ordering='subscription__status')
    def get_subscription_status(self, obj):
        try:
            # hasattr kontrolü, subscription nesnesi henüz oluşmamışsa (nadir durum) hata vermesini engeller
            if hasattr(obj, 'subscription') and obj.subscription:
                return obj.subscription.get_status_display()
        except Subscription.DoesNotExist:
            pass # Bu durumda alttaki None dönecek
        return "Abonelik Yok"

    # YENİ: Abonelik bitiş tarihini göstermek için metot
    @admin.display(description='Abonelik Bitiş', ordering='subscription__expires_at')
    def get_subscription_expires_at(self, obj):
        try:
            if hasattr(obj, 'subscription') and obj.subscription and obj.subscription.expires_at:
                return obj.subscription.expires_at.strftime('%d.%m.%Y')
            return "-"
        except Subscription.DoesNotExist:
            return "-"

# ... Bu dosyada bulunan diğer tüm Admin sınıflarınız (TableAdmin, KDSScreenAdmin, vb.) aynı şekilde kalmalıdır ...
# Sadece BusinessAdmin sınıfını yukarıdaki gibi değiştirmeniz yeterlidir.

@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('table_number', 'business', 'uuid')
    list_filter = ('business',)
    search_fields = ('table_number', 'business__name', 'uuid')
    list_editable = ('table_number',)
    list_display_links = ('uuid',)


@admin.register(KDSScreen)
class KDSScreenAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'slug', 'is_active', 'created_at')
    list_filter = ('business', 'is_active')
    search_fields = ('name', 'slug', 'business__name')
    prepopulated_fields = {'slug': ('business', 'name',)}
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {'fields': ('business', 'name', 'slug')}),
        ('Detaylar ve Durum', {'fields': ('description', 'is_active')}),
        ('Tarihler', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'parent_category_name', 'assigned_kds_name', 'image_tag_preview')
    list_filter = ('business', 'parent', 'assigned_kds')
    search_fields = ('name', 'business__name', 'parent__name', 'assigned_kds__name')
    readonly_fields = ('image_tag_preview',)
    autocomplete_fields = ['parent', 'assigned_kds']

    def parent_category_name(self, obj):
        return obj.parent.name if obj.parent else "-"
    parent_category_name.short_description = 'Üst Kategori'

    def assigned_kds_name(self, obj):
        return obj.assigned_kds.name if obj.assigned_kds else "-"
    assigned_kds_name.short_description = 'Atanmış KDS'
    assigned_kds_name.admin_order_field = 'assigned_kds__name'


    def image_tag_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url if hasattr(obj.image, 'url') else obj.image)
        return "-"
    image_tag_preview.short_description = 'Görsel Önizleme'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'owned_business') and request.user.owned_business:
            return qs.filter(business=request.user.owned_business)
        if hasattr(request.user, 'associated_business') and request.user.associated_business:
            return qs.filter(business=request.user.associated_business)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        user = request.user
        if not user.is_superuser:
            if db_field.name == "business":
                if hasattr(user, 'owned_business') and user.owned_business:
                    kwargs["queryset"] = Business.objects.filter(pk=user.owned_business.pk)
                    kwargs["initial"] = user.owned_business.pk
                    kwargs["disabled"] = True
                elif hasattr(user, 'associated_business') and user.associated_business:
                    kwargs["queryset"] = Business.objects.filter(pk=user.associated_business.pk)
                    kwargs["initial"] = user.associated_business.pk
                    kwargs["disabled"] = True
                else:
                    kwargs["queryset"] = Business.objects.none()
            
            if db_field.name == "assigned_kds":
                target_business = None
                obj_id = request.resolver_match.kwargs.get('object_id')
                if obj_id:
                    category_instance = self.get_object(request, object_id=obj_id)
                    if category_instance:
                        target_business = category_instance.business
                elif hasattr(user, 'owned_business') and user.owned_business:
                    target_business = user.owned_business
                elif hasattr(user, 'associated_business') and user.associated_business:
                    target_business = user.associated_business
                
                if target_business:
                    kwargs["queryset"] = KDSScreen.objects.filter(business=target_business)
                else:
                    pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class MenuItemVariantInline(admin.TabularInline):
    model = MenuItemVariant
    extra = 1
    fields = ('name', 'price', 'is_extra', 'image')

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'category_name', 'description_short', 'image_tag_preview', 'is_campaign_bundle')
    list_filter = ('business', 'category', 'is_campaign_bundle', 'category__assigned_kds')
    search_fields = ('name', 'description', 'business__name', 'category__name', 'category__assigned_kds__name')
    inlines = [MenuItemVariantInline]
    readonly_fields = ('image_tag_preview',)
    list_per_page = 20
    autocomplete_fields = ['category']

    def category_name(self, obj):
        if obj.category:
            kds_name = f" (KDS: {obj.category.assigned_kds.name})" if obj.category.assigned_kds else ""
            return f"{obj.category.name}{kds_name}"
        return "-"
    category_name.short_description = 'Kategori (KDS)'
    category_name.admin_order_field = 'category__name'

    def description_short(self, obj):
        return (obj.description[:75] + '...') if len(obj.description) > 75 else obj.description
    description_short.short_description = 'Açıklama'
    
    def image_tag_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url if hasattr(obj.image, 'url') else obj.image)
        return "-"
    image_tag_preview.short_description = 'Görsel Önizleme'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'owned_business') and request.user.owned_business:
            return qs.filter(business=request.user.owned_business)
        if hasattr(request.user, 'associated_business') and request.user.associated_business:
            return qs.filter(business=request.user.associated_business)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        user = request.user
        if not user.is_superuser:
            if db_field.name == "business":
                if hasattr(user, 'owned_business') and user.owned_business:
                    kwargs["queryset"] = Business.objects.filter(pk=user.owned_business.pk)
                    kwargs["initial"] = user.owned_business.pk
                    kwargs["disabled"] = True
                elif hasattr(user, 'associated_business') and user.associated_business:
                    kwargs["queryset"] = Business.objects.filter(pk=user.associated_business.pk)
                    kwargs["initial"] = user.associated_business.pk
                    kwargs["disabled"] = True
                else:
                    kwargs["queryset"] = Business.objects.none()
            
            if db_field.name == "category":
                target_business = None
                obj_id = request.resolver_match.kwargs.get('object_id')
                if obj_id:
                    menu_item_instance = self.get_object(request, object_id=obj_id)
                    if menu_item_instance:
                        target_business = menu_item_instance.business
                elif hasattr(user, 'owned_business') and user.owned_business:
                    target_business = user.owned_business
                elif hasattr(user, 'associated_business') and user.associated_business:
                    target_business = user.associated_business
                
                if target_business:
                    kwargs["queryset"] = Category.objects.filter(business=target_business)
                else:
                    kwargs["queryset"] = Category.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class OrderItemExtraInline(admin.TabularInline):
    model = OrderItemExtra
    extra = 0
    readonly_fields = ('variant_price',)

    def variant_price(self, obj):
        return obj.variant.price
    variant_price.short_description = "Ekstra Birim Fiyat"

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        'menu_item_name', 'variant_name', 'calculated_price', 
        'is_awaiting_staff_approval', 'get_assigned_kds_for_item',
        'kds_status_display', 'item_prepared_by_staff_username'
    )
    inlines = [OrderItemExtraInline]
    
    fields = (
        'menu_item', 'variant', 'quantity', 'table_user', 
        'delivered', 'price', 'calculated_price', 'is_awaiting_staff_approval', 
        'get_assigned_kds_for_item', 'kds_status', 'item_prepared_by_staff'
    )
    autocomplete_fields = ['menu_item', 'variant', 'item_prepared_by_staff']

    def menu_item_name(self, obj):
        return obj.menu_item.name
    menu_item_name.short_description = "Ürün Adı"
    
    def variant_name(self, obj):
        if obj.variant:
            return obj.variant.name
        return "-"
    variant_name.short_description = "Varyant Adı"

    def calculated_price(self,obj):
        return obj.price
    calculated_price.short_description = "Birim Fiyat (Hesaplanan)"

    def get_assigned_kds_for_item(self, obj):
        if obj.menu_item and obj.menu_item.category and obj.menu_item.category.assigned_kds:
            return obj.menu_item.category.assigned_kds.name
        return "-"
    get_assigned_kds_for_item.short_description = "Atanmış KDS"

    def kds_status_display(self, obj):
        return obj.get_kds_status_display()
    kds_status_display.short_description = "KDS Durumu"

    def item_prepared_by_staff_username(self, obj):
        return obj.item_prepared_by_staff.username if obj.item_prepared_by_staff else "-"
    item_prepared_by_staff_username.short_description = "KDS'te Hazırlayan"

class OrderTableUserInline(admin.TabularInline):
    model = OrderTableUser
    extra = 0

class PaymentInline(admin.StackedInline):
    model = Payment
    can_delete = False
    readonly_fields = ('payment_date',)
    fields = ('payment_type', 'amount', 'payment_date')

class CreditPaymentDetailsInline(admin.StackedInline):
    model = CreditPaymentDetails
    readonly_fields = ('created_at', 'paid_at')
    fields = ('notes', 'created_at', 'paid_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'business', 'table_display', 'order_type', 'status_display',
        'customer_display', 'taken_by_staff_username', 
        'prepared_by_kitchen_staff_username',
        'assigned_pager_display',
        'created_at', 'is_paid', 'kitchen_completed_at', 'delivered_at'
    )
    list_filter = ('business', 'order_type', 'status', 'is_paid', 'created_at', 'is_split_table', 'taken_by_staff', 'prepared_by_kitchen_staff', 'assigned_pager_instance__status')
    search_fields = (
        'id', 'table__table_number', 'customer__username', 'customer_name', 
        'business__name', 'taken_by_staff__username', 'prepared_by_kitchen_staff__username',
        'assigned_pager_instance__device_id', 'assigned_pager_instance__name'
    )
    readonly_fields = ('created_at', 'id', 'kitchen_completed_at', 'delivered_at', 'assigned_pager_display')
    inlines = [OrderItemInline, OrderTableUserInline, PaymentInline, CreditPaymentDetailsInline]
    date_hierarchy = 'created_at'
    list_select_related = ('business', 'table', 'customer', 'taken_by_staff', 'prepared_by_kitchen_staff', 'assigned_pager_instance')
    list_per_page = 25
    
    fieldsets = (
        ("Genel Bilgiler", {
            'fields': ('id', 'business', 'order_type', 'table', 'is_split_table', 'assigned_pager_display') 
        }),
        ("Müşteri Bilgileri", {
            'fields': ('customer', 'customer_name', 'customer_phone')
        }),
        ("Personel ve Durum", {
            'fields': (
                'status',
                'taken_by_staff', 
                'prepared_by_kitchen_staff',
                'is_paid', 
                'created_at',
                'kitchen_completed_at',
                'delivered_at',
            )
        }),
    )

    def status_display(self, obj):
        return obj.get_status_display()
    status_display.short_description = "Durum"
    status_display.admin_order_field = 'status'

    def table_display(self, obj):
        return obj.table.table_number if obj.table else ("Paket" if obj.order_type == 'takeaway' else "-")
    table_display.short_description = "Masa/Tip"

    def customer_display(self, obj):
        if obj.customer:
            return obj.customer.username
        return obj.customer_name or "Misafir"
    customer_display.short_description = "Müşteri"

    def taken_by_staff_username(self, obj):
        return obj.taken_by_staff.username if obj.taken_by_staff else "-"
    taken_by_staff_username.short_description = "Siparişi Alan"
    taken_by_staff_username.admin_order_field = 'taken_by_staff__username'

    def prepared_by_kitchen_staff_username(self, obj):
        return obj.prepared_by_kitchen_staff.username if obj.prepared_by_kitchen_staff else "-"
    prepared_by_kitchen_staff_username.short_description = "Hazırlayan (Mutfak - Genel)"
    prepared_by_kitchen_staff_username.admin_order_field = 'prepared_by_kitchen_staff__username'

    def assigned_pager_display(self, obj: Order) -> str:
        try:
            if hasattr(obj, 'assigned_pager_instance') and obj.assigned_pager_instance:
                pager = obj.assigned_pager_instance
                return f"{pager.name or pager.device_id} ({pager.get_status_display()})"
        except Pager.DoesNotExist:
            return "-"
        except AttributeError:
            return "-"
        return "-"
    assigned_pager_display.short_description = "Atanmış Pager"
    assigned_pager_display.admin_order_field = 'assigned_pager_instance__device_id'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'owned_business') and request.user.owned_business:
            return qs.filter(business=request.user.owned_business)
        if hasattr(request.user, 'associated_business') and request.user.associated_business:
            return qs.filter(business=request.user.associated_business)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        user = request.user
        if not user.is_superuser:
            if db_field.name == "business":
                if hasattr(user, 'owned_business') and user.owned_business:
                    kwargs["queryset"] = Business.objects.filter(pk=user.owned_business.pk)
                    kwargs["initial"] = user.owned_business.pk
                    kwargs["disabled"] = True
                elif hasattr(user, 'associated_business') and user.associated_business:
                    kwargs["queryset"] = Business.objects.filter(pk=user.associated_business.pk)
                    kwargs["initial"] = user.associated_business.pk
                    kwargs["disabled"] = True
                else:
                    kwargs["queryset"] = Business.objects.none()
            elif db_field.name in ["taken_by_staff", "prepared_by_kitchen_staff"]:
                target_business = None
                obj_id = request.resolver_match.kwargs.get('object_id')
                if obj_id:
                    order_instance = self.get_object(request, object_id=obj_id)
                    if order_instance:
                        target_business = order_instance.business
                elif hasattr(user, 'owned_business') and user.owned_business:
                    target_business = user.owned_business
                elif hasattr(user, 'associated_business') and user.associated_business:
                    target_business = user.associated_business

                if target_business:
                    if db_field.name == "taken_by_staff":
                        kwargs["queryset"] = CustomUser.objects.filter(
                            models.Q(associated_business=target_business, user_type='staff') |
                            models.Q(owned_business=target_business, user_type='business_owner')
                        ).distinct()
                    elif db_field.name == "prepared_by_kitchen_staff":
                        kwargs["queryset"] = CustomUser.objects.filter(
                            models.Q(associated_business=target_business, user_type__in=['kitchen_staff', 'staff']) |
                            models.Q(owned_business=target_business, user_type='business_owner')
                        ).distinct()
                else:
                    kwargs["queryset"] = CustomUser.objects.none()
            elif db_field.name == "table":
                target_business = None
                obj_id = request.resolver_match.kwargs.get('object_id')
                if obj_id:
                    order_instance = self.get_object(request, object_id=obj_id)
                    if order_instance:
                        target_business = order_instance.business
                elif hasattr(user, 'owned_business') and user.owned_business:
                    target_business = user.owned_business
                elif hasattr(user, 'associated_business') and user.associated_business:
                    target_business = user.associated_business
                
                if target_business:
                    kwargs["queryset"] = Table.objects.filter(business=target_business)
                else:
                    kwargs["queryset"] = Table.objects.none()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order_id_display', 'payment_type', 'amount', 'payment_date')
    list_filter = ('payment_type', 'payment_date', 'order__business')
    search_fields = ('order__id', 'order__customer_name', 'order__customer__username')
    readonly_fields = ('payment_date',)
    date_hierarchy = 'payment_date'

    def order_id_display(self, obj):
        return obj.order.id
    order_id_display.short_description = 'Sipariş ID'
    order_id_display.admin_order_field = 'order__id'


@admin.register(MenuItemVariant)
class MenuItemVariantAdmin(admin.ModelAdmin):
    list_display = ('name', 'menu_item_name', 'price', 'is_extra', 'image_tag_preview')
    list_filter = ('menu_item__business', 'is_extra', 'menu_item__category', 'menu_item')
    search_fields = ('name', 'menu_item__name')
    readonly_fields = ('image_tag_preview',)
    list_select_related = ('menu_item', 'menu_item__business')

    def menu_item_name(self, obj):
        return obj.menu_item.name
    menu_item_name.short_description = 'Ana Ürün'
    menu_item_name.admin_order_field = 'menu_item__name'

    def image_tag_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url if hasattr(obj.image, 'url') else obj.image)
        return "-"
    image_tag_preview.short_description = 'Görsel Önizleme'

# ----- GÜNCELLENEN Admin Sınıfı: StockAdmin -----
@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    # Yeni alanlar list_display'e eklendi
    list_display = ('variant_display', 'quantity', 'track_stock', 'alert_threshold', 'business_name', 'last_updated')
    # track_stock filtresi eklendi
    list_filter = ('variant__menu_item__business', 'track_stock', 'last_updated')
    search_fields = ('variant__name', 'variant__menu_item__name', 'variant__menu_item__business__name')
    readonly_fields = ('last_updated',)
    list_select_related = ('variant', 'variant__menu_item', 'variant__menu_item__business')
    # Yeni alanlar düzenlenebilir yapıldı
    list_editable = ('quantity', 'track_stock', 'alert_threshold')

    def variant_display(self, obj):
        return f"{obj.variant.menu_item.name} - {obj.variant.name}"
    variant_display.short_description = 'Ürün Varyantı'
    variant_display.admin_order_field = 'variant__name'
    
    def business_name(self, obj):
        return obj.variant.menu_item.business.name
    business_name.short_description = 'İşletme'
    business_name.admin_order_field = 'variant__menu_item__business__name'
# ----- GÜNCELLEME SONU -----

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('variant_name_display', 'movement_type_display', 'quantity_change', 'quantity_before','quantity_after', 'user_display', 'timestamp', 'related_order_id_display')
    list_filter = ('movement_type', 'variant__menu_item__business', 'user', 'timestamp')
    search_fields = ('variant__name', 'variant__menu_item__name', 'user__username', 'description', 'related_order__id')
    readonly_fields = ('quantity_before', 'quantity_after', 'timestamp', 'user', 'stock', 'variant', 'related_order')
    date_hierarchy = 'timestamp'
    list_per_page = 25
    list_select_related = ('variant', 'variant__menu_item', 'user', 'related_order', 'stock')

    def variant_name_display(self, obj):
        return f"{obj.variant.menu_item.name} ({obj.variant.name})"
    variant_name_display.short_description = 'Ürün Varyantı'
    variant_name_display.admin_order_field = 'variant__menu_item__name'

    def movement_type_display(self, obj):
        return obj.get_movement_type_display()
    movement_type_display.short_description = 'Hareket Tipi'
    movement_type_display.admin_order_field = 'movement_type'

    def user_display(self, obj):
        return obj.user.username if obj.user else "-"
    user_display.short_description = 'Kullanıcı'
    user_display.admin_order_field = 'user__username'

    def related_order_id_display(self, obj):
        return obj.related_order.id if obj.related_order else '-'
    related_order_id_display.short_description = 'İlişkili Sipariş ID'
    related_order_id_display.admin_order_field = 'related_order__id'


@admin.register(WaitingCustomer)
class WaitingCustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'business', 'party_size', 'is_waiting', 'created_at', 'called_at', 'seated_at')
    list_filter = ('is_waiting', 'business', 'created_at')
    search_fields = ('name', 'phone', 'business__name')
    readonly_fields = ('created_at', 'called_at', 'seated_at')
    list_editable = ('is_waiting',)
    fieldsets = (
        (None, {'fields': ('business', 'name', 'phone', 'party_size', 'notes')}),
        ('Durum ve Zamanlar', {'fields': ('is_waiting', 'created_at', 'called_at', 'seated_at')}),
    )

@admin.register(CreditPaymentDetails)
class CreditPaymentDetailsAdmin(admin.ModelAdmin):
    list_display = ('order_id_display', 'get_customer_name', 'get_customer_phone', 'notes_short', 'created_at', 'paid_at')
    list_filter = ('paid_at', 'created_at', 'order__business')
    search_fields = ('order__id', 'order__customer_name', 'order__customer__username', 'notes')
    readonly_fields = ('created_at', 'paid_at', 'order')
    date_hierarchy = 'created_at'
    list_select_related = ('order', 'order__customer')

    def order_id_display(self, obj):
        return obj.order.id
    order_id_display.short_description = 'Sipariş ID'
    order_id_display.admin_order_field = 'order__id'

    def get_customer_name(self, obj):
        if obj.order.customer:
            return obj.order.customer.get_full_name() or obj.order.customer.username
        return obj.order.customer_name or "Misafir"
    get_customer_name.short_description = 'Müşteri Adı'
    get_customer_name.admin_order_field = 'order__customer_name'

    def get_customer_phone(self, obj):
        return obj.order.customer_phone or "-"
    get_customer_phone.short_description = 'Müşteri Telefon'
    get_customer_phone.admin_order_field = 'order__customer_phone'

    def notes_short(self, obj):
        return (obj.notes[:50] + '...') if obj.notes and len(obj.notes) > 50 else obj.notes
    notes_short.short_description = 'Notlar'

@admin.register(Pager)
class PagerAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'name', 'get_business_name', 'get_status_display_with_color', 'get_current_order_info', 'last_status_update', 'notes_short_display')
    list_filter = ('business', 'status')
    search_fields = ('device_id', 'name', 'business__name', 'current_order__id', 'current_order__customer_name')
    list_editable = ('name',)
    readonly_fields = ('last_status_update',)
    raw_id_fields = ('current_order',)
    list_per_page = 25
    list_select_related = ('business', 'current_order', 'current_order__table')

    fieldsets = (
        (None, {'fields': ('business', 'device_id', 'name')}),
        ('Durum ve Atama Bilgileri', {'fields': ('status', 'current_order', 'last_status_update')}),
        ('Ek Notlar', {'fields': ('notes',)}),
    )

    def get_business_name(self, obj: Pager) -> str:
        return obj.business.name
    get_business_name.short_description = "İşletme"
    get_business_name.admin_order_field = 'business__name'

    def get_status_display_with_color(self, obj: Pager) -> str:
        status_val = obj.status
        display_text = obj.get_status_display()
        color = "black"
        if status_val == 'available': color = "green"
        elif status_val == 'in_use': color = "orange"
        elif status_val == 'charging': color = "blue"
        elif status_val == 'low_battery': color = "darkorange"
        elif status_val == 'out_of_service': color = "red"
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, display_text)
    get_status_display_with_color.short_description = "Durum"
    get_status_display_with_color.admin_order_field = 'status'

    def get_current_order_info(self, obj: Pager) -> str:
        if obj.current_order:
            order = obj.current_order
            table_info = f"Masa {order.table.table_number}" if order.table else "Paket"
            customer_info = order.customer_name or (order.customer.username if order.customer else "Misafir")
            return f"#{order.id} ({table_info} - {customer_info})"
        return "-"
    get_current_order_info.short_description = "Atanmış Sipariş"
    get_current_order_info.admin_order_field = 'current_order__id'

    def notes_short_display(self, obj: Pager) -> str:
        if obj.notes and len(obj.notes) > 30:
            return obj.notes[:30] + "..."
        return obj.notes or "-"
    notes_short_display.short_description = "Notlar"


class CampaignMenuItemInline(admin.TabularInline):
    model = CampaignMenuItem
    extra = 1
    autocomplete_fields = ['menu_item', 'variant']

@admin.register(CampaignMenu)
class CampaignMenuAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'campaign_price', 'is_active', 'start_date', 'end_date', 'image_tag_preview', 'bundle_menu_item_info')
    list_filter = ('business', 'is_active', 'start_date', 'end_date')
    search_fields = ('name', 'description', 'business__name')
    inlines = [CampaignMenuItemInline]
    readonly_fields = ('image_tag_preview', 'bundle_menu_item_info')
    list_editable = ('is_active', 'campaign_price')

    def image_tag_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url if hasattr(obj.image, 'url') else obj.image)
        return "-"
    image_tag_preview.short_description = 'Görsel Önizleme'

    def bundle_menu_item_info(self, obj):
        if obj.bundle_menu_item:
            return f"ID: {obj.bundle_menu_item.id} - Ad: {obj.bundle_menu_item.name}"
        return "İlişkili Ürün Yok"
    bundle_menu_item_info.short_description = 'Kampanya Menü Öğesi (Sistem)'

@admin.register(CampaignMenuItem)
class CampaignMenuItemAdmin(admin.ModelAdmin):
    list_display = ('campaign_menu', 'menu_item_display', 'variant_display', 'quantity')
    list_filter = ('campaign_menu__business', 'campaign_menu', 'menu_item__category')
    search_fields = ('campaign_menu__name', 'menu_item__name', 'variant__name')
    list_select_related = ('campaign_menu', 'menu_item', 'variant', 'menu_item__category')
    autocomplete_fields = ['campaign_menu', 'menu_item', 'variant']

    def menu_item_display(self, obj):
        return obj.menu_item.name
    menu_item_display.short_description = "Ana Ürün"

    def variant_display(self, obj):
        return obj.variant.name if obj.variant else "-"
    variant_display.short_description = "Varyant"