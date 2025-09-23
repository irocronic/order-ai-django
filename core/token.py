# core/token.py

from datetime import timezone as dt_timezone, timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
import pytz

# Gerekli modelleri import ediyoruz
from .models import Business, ScheduledShift, NOTIFICATION_EVENT_TYPES
from .serializers.kds_serializers import KDSScreenSerializer
from subscriptions.models import Subscription, Plan

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['user_type'] = user.user_type
        token['user_id'] = user.id
        token['profile_image_url'] = user.profile_image_url

        business = None
        # === GÜNCELLEME BAŞLANGICI: Admin kullanıcısı için özel token verisi ===
        if user.user_type == 'admin' or user.is_superuser:
            # Admin için işletme bilgisi yok, varsayılan/özel değerler atanır
            token['business_id'] = None
            token['is_setup_complete'] = True # Adminin kurulum yapmasına gerek yok
            token['currency_code'] = 'TRY' # Varsayılan para birimi
            token['subscription_status'] = 'active' # Adminin aboneliği her zaman aktif kabul edilir
            token['trial_ends_at'] = None
            token['subscription'] = {'plan_name': 'Admin Plan'} # Özel bir plan adı
            token['staff_permissions'] = []
            # Admin tüm bildirimleri alabilir
            token['notification_permissions'] = [key for key, desc in NOTIFICATION_EVENT_TYPES]
            token['accessible_kds_screens_details'] = []

        elif user.user_type == 'business_owner':
        # === GÜNCELLEME SONU ===
            business = getattr(user, 'owned_business', None)
        elif user.user_type in ['staff', 'kitchen_staff']:
            business = getattr(user, 'associated_business', None)
            token['staff_permissions'] = user.staff_permissions
            token['notification_permissions'] = user.notification_permissions
            if hasattr(user, 'accessible_kds_screens') and user.accessible_kds_screens.exists():
                accessible_kds_data = KDSScreenSerializer(user.accessible_kds_screens.all(), many=True).data
                token['accessible_kds_screens_details'] = accessible_kds_data
            else:
                token['accessible_kds_screens_details'] = []
        else: # customer
            token['notification_permissions'] = user.notification_permissions
            token['accessible_kds_screens_details'] = []

        if business:
            token['business_id'] = business.id
            token['is_setup_complete'] = business.is_setup_complete
            token['currency_code'] = business.currency_code
            
            try:
                subscription = business.subscription
                token['subscription_status'] = subscription.status
                token['trial_ends_at'] = subscription.expires_at.isoformat() if subscription.status == 'trial' and subscription.expires_at else None
                
                if subscription.plan:
                    plan_data = {
                        'plan_name': subscription.plan.name,
                        'max_tables': subscription.plan.max_tables,
                        'max_staff': subscription.plan.max_staff,
                        'max_kds_screens': subscription.plan.max_kds_screens,
                        'max_categories': subscription.plan.max_categories,
                        'max_menu_items': subscription.plan.max_menu_items,
                        'max_variants': subscription.plan.max_variants,
                    }
                    token['subscription'] = plan_data
                else:
                    token['subscription'] = None
            except Subscription.DoesNotExist:
                token['subscription_status'] = 'inactive'
                token['trial_ends_at'] = None
                token['subscription'] = None
        elif user.user_type not in ['admin', 'customer']: # Admin ve customer dışındakiler için boş değerler
            token['business_id'] = None
            token['is_setup_complete'] = False
            token['currency_code'] = None
            token['subscription_status'] = None
            token['trial_ends_at'] = None
        
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        if not user.is_active:
            raise AuthenticationFailed(
                "Hesabınız aktif değil. Lütfen yönetici ile iletişime geçin veya onay bekleyin.",
                "account_inactive"
            )
        
        # === YENİ KONTROL: Admin ise diğer kontrolleri atla ===
        if user.user_type == 'admin' or user.is_superuser:
            pass # Admin, vardiya ve abonelik kontrollerinden muaftır.
        # === KONTROL SONU ===
        elif user.user_type in ['staff', 'kitchen_staff']:
            if not user.is_superuser:
                business = user.associated_business
                if not business:
                    raise AuthenticationFailed("Bir işletmeye atanmamışsınız.", "no_business_assigned")
                
                try:
                    business_tz = pytz.timezone(business.timezone)
                except pytz.UnknownTimeZoneError:
                    business_tz = pytz.timezone(settings.TIME_ZONE) 

                now_in_business_tz = timezone.now().astimezone(business_tz)
                today = now_in_business_tz.date()
                yesterday = today - timedelta(days=1)
                current_time = now_in_business_tz.time()
                
                potential_shifts = ScheduledShift.objects.filter(
                    staff=user,
                    date__in=[today, yesterday]
                ).select_related('shift')

                if not potential_shifts.exists():
                    raise AuthenticationFailed(
                        'Bugün için planlanmış bir vardiyanız bulunmadığından giriş yapamazsınız.',
                        'no_shift_scheduled'
                    )
                
                is_on_active_shift = False
                for scheduled_shift in potential_shifts:
                    shift = scheduled_shift.shift
                    if shift.start_time <= shift.end_time:
                        if scheduled_shift.date == today and shift.start_time <= current_time <= shift.end_time:
                            is_on_active_shift = True
                            break
                    else:
                        if (scheduled_shift.date == today and current_time >= shift.start_time) or \
                           (scheduled_shift.date == yesterday and current_time <= shift.end_time):
                            is_on_active_shift = True
                            break
                
                if not is_on_active_shift:
                    raise AuthenticationFailed(
                        'Şu an aktif bir çalışma vardiyanız bulunmuyor. Lütfen vardiya saatleriniz içinde tekrar deneyin.',
                        'no_active_shift_at_login'
                    )

        elif self.user.user_type == 'business_owner':
            business = getattr(self.user, 'owned_business', None)
            if not business:
                raise AuthenticationFailed('Bu kullanıcıya ait bir işletme bulunamadı.', code='no_business_found')
            
            try:
                subscription = business.subscription
                if subscription.status in ['inactive', 'cancelled']:
                        raise AuthenticationFailed(
                            'Aboneliğiniz aktif değildir. Lütfen bir abonelik paketi seçin.',
                            code='subscription_expired'
                        )
                if subscription.status == 'trial' and subscription.expires_at and subscription.expires_at < timezone.now():
                    raise AuthenticationFailed(
                        'Deneme süreniz sona ermiştir. Lütfen bir abonelik paketi seçin.',
                        code='subscription_expired'
                    )
            except Subscription.DoesNotExist:
                    raise AuthenticationFailed(
                        'Abonelik bilgileriniz bulunamadı. Lütfen destek ile iletişime geçin.',
                        code='subscription_error'
                    )
        
        refresh = self.get_token(self.user)
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        
        # Token payload'ındaki tüm veriyi response'a ekle
        data.update(refresh.payload)

        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer