# core/serializers/admin_serializers.py

from rest_framework import serializers
# GÜNCELLENMİŞ: timezone import edildi
from django.utils import timezone
from ..models import Business, CustomUser as User, NotificationSetting, KDSScreen, NOTIFICATION_EVENT_TYPES, STAFF_PERMISSION_CHOICES
from .kds_serializers import KDSScreenSerializer

class BusinessForAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'name', 'address']

class AdminBusinessOwnerSerializer(serializers.ModelSerializer):
    owned_business_details = BusinessForAdminSerializer(source='owned_business', read_only=True)
    staff_count = serializers.SerializerMethodField()
    is_approved_by_admin = serializers.BooleanField(read_only=True)
    notification_permissions = serializers.ListField(child=serializers.CharField(), read_only=True)
    accessible_kds_screens_details = KDSScreenSerializer(source='accessible_kds_screens', many=True, read_only=True)
    profile_image_url = serializers.URLField(read_only=True)
    
    # === YENİ ALANLAR BURAYA EKLENİYOR ===
    subscription_plan_name = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()
    trial_days_remaining = serializers.SerializerMethodField()
    # === /YENİ ALANLAR ===

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'is_active', 'is_approved_by_admin', 'date_joined',
            'user_type', 'owned_business_details', 'staff_count',
            'staff_permissions', 'notification_permissions',
            'accessible_kds_screens_details',
            'profile_image_url',
            # === YENİ ALANLAR fields listesine ekleniyor ===
            'subscription_plan_name',
            'subscription_status',
            'trial_days_remaining',
        ]
        read_only_fields = fields

    def get_staff_count(self, obj):
        try:
            if hasattr(obj, 'owned_business') and obj.owned_business:
                return obj.owned_business.staff_members.filter(user_type__in=['staff', 'kitchen_staff']).count()
            return 0
        except Business.DoesNotExist:
            return 0
        except AttributeError:
            return 0

    # === YENİ METOTLAR BURAYA EKLENİYOR ===
    def get_subscription_plan_name(self, obj):
        try:
            # Kullanıcının işletmesi, işletmenin aboneliği ve aboneliğin planı var mı diye kontrol et
            if hasattr(obj, 'owned_business') and obj.owned_business and hasattr(obj.owned_business, 'subscription') and obj.owned_business.subscription.plan:
                return obj.owned_business.subscription.plan.name
            return "Plansız"
        except Exception:
            return "Bilinmiyor"

    def get_subscription_status(self, obj):
        try:
            if hasattr(obj, 'owned_business') and obj.owned_business and hasattr(obj.owned_business, 'subscription'):
                return obj.owned_business.subscription.get_status_display()
            return "Abonelik Yok"
        except Exception:
            return "Bilinmiyor"

    def get_trial_days_remaining(self, obj):
        try:
            if hasattr(obj, 'owned_business') and obj.owned_business and hasattr(obj.owned_business, 'subscription'):
                sub = obj.owned_business.subscription
                if sub.status == 'trial' and sub.expires_at:
                    delta = sub.expires_at - timezone.now()
                    # Eğer süre dolmuşsa 0, dolmamışsa gün sayısını döndür
                    return max(0, delta.days)
            return None # Deneme süresinde değilse veya süre bitmişse null döner
        except Exception:
            return None
    # === /YENİ METOTLAR ===

class AdminStaffUserSerializer(serializers.ModelSerializer):
    is_approved_by_admin = serializers.BooleanField(read_only=True)
    notification_permissions = serializers.ListField(child=serializers.CharField(), read_only=True)
    associated_business_name = serializers.CharField(source='associated_business.name', read_only=True, allow_null=True)
    accessible_kds_screens_details = KDSScreenSerializer(source='accessible_kds_screens', many=True, read_only=True)
    profile_image_url = serializers.URLField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'is_active', 'is_approved_by_admin', 'date_joined',
            'user_type', 'associated_business_name',
            'staff_permissions', 'notification_permissions',
            'accessible_kds_screens_details',
            'profile_image_url'
        ]
        read_only_fields = fields

class UserActivationSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=True)

class AdminUserNotificationPermissionUpdateSerializer(serializers.ModelSerializer):
    notification_permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=[choice[0] for choice in NOTIFICATION_EVENT_TYPES]),
        required=False, 
        allow_empty=True
    )
    accessible_kds_screen_ids = serializers.PrimaryKeyRelatedField(
        queryset=KDSScreen.objects.all(),
        source='accessible_kds_screens',
        many=True,
        required=False, 
        allow_empty=True,
        help_text="Kullanıcının erişebileceği KDS ekranlarının ID listesi (Admin için)."
    )

    class Meta:
        model = User
        fields = ['notification_permissions', 'accessible_kds_screen_ids']

    def update(self, instance, validated_data):
        if 'notification_permissions' in validated_data:
            instance.notification_permissions = validated_data.get('notification_permissions', instance.notification_permissions)
        
        if 'accessible_kds_screens' in validated_data:
            accessible_kds_data = validated_data.get('accessible_kds_screens')
            instance.accessible_kds_screens.set(accessible_kds_data)
        
        fields_to_update = []
        if 'notification_permissions' in validated_data:
            fields_to_update.append('notification_permissions')
        
        if fields_to_update:
            instance.save(update_fields=fields_to_update)
        elif 'accessible_kds_screens' in validated_data:
            instance.save() 
            
        return instance

class NotificationSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSetting
        fields = ['event_type', 'is_active', 'description']