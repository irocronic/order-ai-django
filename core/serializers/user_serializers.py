# core/serializers/user_serializers.py
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from rest_framework.exceptions import ValidationError, PermissionDenied

from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import smart_str, DjangoUnicodeDecodeError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.conf import settings

from ..models import CustomUser as User, Business, STAFF_PERMISSION_CHOICES, NOTIFICATION_EVENT_TYPES, KDSScreen
from .kds_serializers import KDSScreenSerializer

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'user_type']
        extra_kwargs = {
            'user_type': {'required': True}
        }

    def validate_user_type(self, value):
        allowed_public_registration_types = ['customer', 'business_owner']
        if value not in allowed_public_registration_types:
            raise serializers.ValidationError(
                f"Bu endpoint üzerinden sadece '{', '.join(allowed_public_registration_types)}' tipleri için kayıt yapılabilir."
            )
        return value
        
    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Bu e-posta adresi zaten kayıtlı.")
        return value

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
            user_type=validated_data['user_type'],
            is_active=False, 
            is_approved_by_admin=False 
        )
        user.set_password(validated_data['password'])
        user.save()
        
        if validated_data['user_type'] == 'business_owner':
            if not hasattr(user, 'owned_business'):
                Business.objects.create(
                    owner=user, 
                    name=f"{validated_data['username']}",
                    address="Lütfen Adresi Güncelleyin"
                )
        
        if user.user_type in ['customer', 'business_owner'] and not user.is_approved_by_admin:
            if settings.ADMIN_EMAIL_RECIPIENTS:
                subject = f"Yeni Üyelik Talebi: {user.username} ({user.get_user_type_display()})"
                message = f"""Merhaba Admin,

Sisteme yeni bir üyelik talebi geldi. Lütfen kullanıcıyı onaylamak veya reddetmek için admin panelini ziyaret edin.

Kullanıcı Bilgileri:
- Kullanıcı Adı: {user.username}
- E-posta: {user.email}
- Kullanıcı Tipi: {user.get_user_type_display()}
- Kayıt Tarihi: {user.date_joined.strftime('%d/%m/%Y %H:%M')}

Teşekkürler,
Makarna App Sistemi
"""
                try:
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        settings.ADMIN_EMAIL_RECIPIENTS,
                        fail_silently=False,
                    )
                    print(f"Adminlere yeni üyelik bildirimi gönderildi: {user.username}")
                except Exception as e:
                    print(f"Adminlere yeni üyelik bildirimi gönderilirken HATA: {e}")
            else:
                print("UYARI: Yeni üyelik bildirimi için admin e-posta adresleri tanımlanmamış (ADMIN_EMAIL_RECIPIENTS).")
        
        return user


class AccountSettingsSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True)
    user_type_display = serializers.CharField(source='get_user_type_display', read_only=True)
    old_password = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    new_password = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    confirm_new_password = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    notification_permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=[choice[0] for choice in NOTIFICATION_EVENT_TYPES]),
        required=False,
        allow_empty=True
    )
    accessible_kds_screens_details = KDSScreenSerializer(source='accessible_kds_screens', many=True, read_only=True)
    profile_image_url = serializers.URLField(max_length=1024, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'user_type_display', 'first_name', 'last_name',
            'old_password', 'new_password', 'confirm_new_password',
            'notification_permissions', 'accessible_kds_screens_details',
            'profile_image_url'
        ]
        read_only_fields = ['id', 'username', 'user_type_display', 'accessible_kds_screens_details']

    def validate_email(self, value):
        if self.instance and value and self.instance.email != value and User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("Bu e-posta adresi zaten başka bir kullanıcı tarafından kullanılıyor.")
        return value

    def validate(self, attrs):
        old_password = attrs.get('old_password')
        new_password = attrs.get('new_password')
        confirm_new_password = attrs.get('confirm_new_password')

        if any([old_password, new_password, confirm_new_password]):
            if not all([old_password, new_password, confirm_new_password]):
                raise serializers.ValidationError(
                    "Parola değiştirmek için mevcut parolanızı, yeni parolanızı ve yeni parolanın tekrarını girmelisiniz."
                )
            if not self.instance.check_password(old_password):
                raise serializers.ValidationError({'old_password': 'Mevcut parolanız yanlış.'})
            if new_password != confirm_new_password:
                raise serializers.ValidationError({'confirm_new_password': 'Yeni parolalar eşleşmiyor.'})
        return attrs

    def update(self, instance, validated_data):
        instance.profile_image_url = validated_data.get('profile_image_url', instance.profile_image_url)
        instance.email = validated_data.get('email', instance.email)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        
        if 'notification_permissions' in validated_data:
            instance.notification_permissions = validated_data.get('notification_permissions', instance.notification_permissions)

        new_password = validated_data.get('new_password')
        if new_password:
            instance.set_password(new_password)

        instance.save()
        return instance

class StaffUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'}, allow_blank=True, allow_null=True)
    staff_permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=[choice[0] for choice in STAFF_PERMISSION_CHOICES]),
        required=False,
        allow_empty=True
    )
    notification_permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=[choice[0] for choice in NOTIFICATION_EVENT_TYPES]),
        required=False,
        allow_empty=True
    )
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    
    accessible_kds_screens_details = KDSScreenSerializer(source='accessible_kds_screens', many=True, read_only=True)
    accessible_kds_screen_ids = serializers.PrimaryKeyRelatedField(
        queryset=KDSScreen.objects.all(), 
        source='accessible_kds_screens',
        many=True,
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="Personelin erişebileceği KDS ekranlarının ID listesi."
    )
    profile_image_url = serializers.URLField(max_length=1024, required=False, allow_blank=True, allow_null=True)


    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password', 'first_name', 'last_name', 
            'is_active', 'staff_permissions', 'notification_permissions',
            'user_type', 'associated_business',
            'accessible_kds_screens_details', 'accessible_kds_screen_ids',
            'profile_image_url'
        ]
        read_only_fields = ['id', 'user_type', 'associated_business', 'accessible_kds_screens_details']
        extra_kwargs = {
            'notification_permissions': {'required': False},
            'accessible_kds_screen_ids': {'required': False}
        }

    def validate_password(self, value):
        if not self.instance and not value:
            raise serializers.ValidationError("Yeni personel için şifre gereklidir.")
        if value and len(value) < 6 : 
            raise serializers.ValidationError("Şifre en az 6 karakter olmalıdır.")
        return value
    
    def validate_email(self, value):
        if value:
            qs = User.objects.filter(email__iexact=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("Bu e-posta adresi zaten başka bir kullanıcı tarafından kullanılıyor.")
        return value

    def validate_accessible_kds_screen_ids(self, kds_screens_list):
        return kds_screens_list

    def create(self, validated_data):
        accessible_kds_data = validated_data.pop('accessible_kds_screens', [])
        password = validated_data.pop('password')
        
        user = User(**validated_data)
        user.set_password(password)
        user.is_staff = False 
        user.is_superuser = False
        user.is_approved_by_admin = True
        user.save()
        
        if accessible_kds_data:
            user.accessible_kds_screens.set(accessible_kds_data)
        return user

    def update(self, instance, validated_data):
        accessible_kds_data = validated_data.pop('accessible_kds_screens', None)
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)

        instance.profile_image_url = validated_data.get('profile_image_url', instance.profile_image_url)
        instance.email = validated_data.get('email', instance.email)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.staff_permissions = validated_data.get('staff_permissions', instance.staff_permissions)
        instance.notification_permissions = validated_data.get('notification_permissions', instance.notification_permissions)
        
        instance.save()

        if accessible_kds_data is not None:
            instance.accessible_kds_screens.set(accessible_kds_data)
            
        return instance


class StaffPermissionUpdateSerializer(serializers.ModelSerializer):
    staff_permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=[choice[0] for choice in STAFF_PERMISSION_CHOICES]),
        required=True, 
        allow_empty=True 
    )

    class Meta:
        model = User
        fields = ['staff_permissions']

    def update(self, instance, validated_data):
        if instance.user_type not in ['staff', 'kitchen_staff']:
            raise PermissionDenied("Sadece 'Personel' veya 'Mutfak Personeli' tipindeki kullanıcıların izinleri düzenlenebilir.")
        
        instance.staff_permissions = validated_data.get('staff_permissions', instance.staff_permissions)
        instance.save(update_fields=['staff_permissions'])
        return instance

class StaffNotificationPermissionUpdateSerializer(serializers.ModelSerializer):
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
        help_text="Personelin erişebileceği KDS ekranlarının ID listesi."
    )

    class Meta:
        model = User
        fields = ['notification_permissions', 'accessible_kds_screen_ids']

    def update(self, instance, validated_data):
        if instance.user_type not in ['staff', 'kitchen_staff', 'business_owner']:
            raise PermissionDenied("Sadece personel veya mutfak personeli kullanıcılarının bildirim/KDS izinleri bu arayüzden düzenlenebilir.")
        
        updated_fields = []
        if 'notification_permissions' in validated_data:
            instance.notification_permissions = validated_data.get('notification_permissions', instance.notification_permissions)
            updated_fields.append('notification_permissions')
        
        if 'accessible_kds_screens' in validated_data:
            accessible_kds_data = validated_data.get('accessible_kds_screens')
            instance.accessible_kds_screens.set(accessible_kds_data)
        
        if updated_fields:
            instance.save(update_fields=updated_fields)
        elif 'accessible_kds_screens' in validated_data:
            instance.save() 
            
        return instance

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Bu e-posta adresi ile kayıtlı bir kullanıcı bulunamadı.")
        return value

class PasswordResetCodeConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True)
    code = serializers.CharField(write_only=True, min_length=6, max_length=6)
    new_password1 = serializers.CharField(write_only=True, style={'input_type': 'password'}, min_length=6)
    new_password2 = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_email(self, value):
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Bu e-posta adresi ile kayıtlı bir kullanıcı bulunamadı.")
        return value

    def validate(self, attrs):
        if attrs['new_password1'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password2": "Yeni şifreler eşleşmiyor."})
        return attrs