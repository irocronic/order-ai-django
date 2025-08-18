# core/views/auth_views.py

from rest_framework import status, generics
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
import random
from django.core.cache import cache

from ..serializers import (
    RegisterSerializer,
    PasswordResetRequestSerializer,
    PasswordResetCodeConfirmSerializer,
)
from ..models import Business

User = get_user_model()

class RegisterView(APIView): # <<< HATA DÜZELTİLDİ: Sınıf adı 'UserRegisterView' yerine 'RegisterView' olarak değiştirildi.
    """
    Yeni bir 'business_owner' veya 'customer' kullanıcısı oluşturur.
    İşletme sahibi kaydolduğunda, bir 'Business' nesnesi de oluşturulur
    ve abonelik durumu 'trial' (deneme) olarak ayarlanır.
    Kullanıcı hesabı, yönetici onayı gerektirmeden direkt aktif olur.
    """
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save() # Serializer'ın create metodu çağrılır

            # --- GÜNCELLENEN BÖLÜM: Otomatik Aktivasyon ve Deneme Süresi ---
            # Kullanıcıyı direkt aktif hale getiriyoruz, yönetici onayı beklemiyoruz.
            user.is_active = True
            user.is_approved_by_admin = True # Bu alan artık eski sistem için, true yapıyoruz.
            user.save()

            # Eğer yeni kullanıcı bir işletme sahibiyse,
            # Business modeli save() metodunda deneme süresini otomatik başlatacak.
            # Business'ın oluşturulduğundan emin olalım (eğer serializer'da değilse).
            if user.user_type == 'business_owner' and not hasattr(user, 'owned_business'):
                 Business.objects.create(
                    owner=user, 
                    name=f"{user.username}'s Business", 
                    address="Lütfen güncelleyin"
                )
            # --- /GÜNCELLENEN BÖLÜM ---

            return Response({
                "user": serializer.data,
                "message": "Kayıt başarılı. 7 günlük deneme süreniz başlamıştır."
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get_serializer(self, *args, **kwargs):
        return self.serializer_class(*args, **kwargs)


class PasswordResetRequestView(generics.GenericAPIView):
    """
    Kullanıcının e-posta adresini alarak şifre sıfırlama kodu gönderir.
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "Eğer bu e-posta adresi sistemimizde kayıtlıysa, şifre sıfırlama kodu gönderilecektir."},
                status=status.HTTP_200_OK
            )

        reset_code = str(random.randint(100000, 999999))
        
        cache_key = f"password_reset_code_{user.email}"
        cache.set(cache_key, reset_code, timeout=300) # 300 saniye = 5 dakika

        subject = 'Makarna App Şifre Sıfırlama Kodu'
        message_text = f"""Merhaba {user.username or user.get_full_name() or 'Kullanıcı'},

Makarna App hesabınız için bir şifre sıfırlama talebinde bulundunuz.
Şifrenizi sıfırlamak için aşağıdaki 6 haneli kodu Flutter uygulamasındaki ilgili alana girin:

Doğrulama Kodu: {reset_code}

Bu kod 5 dakika boyunca geçerlidir. Eğer bu isteği siz yapmadıysanız, bu e-postayı görmezden gelebilirsiniz.

Teşekkürler,
Makarna App Ekibi
"""
        try:
            send_mail(
                subject,
                message_text,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"PasswordResetRequestView: E-posta gönderilirken hata: {e}")
            pass 

        return Response(
            {"detail": "Eğer bu e-posta adresi sistemimizde kayıtlıysa, şifre sıfırlama kodu gönderilecektir."},
            status=status.HTTP_200_OK
        )


class PasswordResetCodeConfirmView(generics.GenericAPIView):
    """
    Kullanıcının girdiği sıfırlama kodunu ve yeni şifreyi alarak şifreyi günceller.
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetCodeConfirmSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        new_password = serializer.validated_data['new_password1']

        cache_key = f"password_reset_code_{email}"
        stored_code = cache.get(cache_key)

        if stored_code is None:
            return Response(
                {"detail": "Şifre sıfırlama kodunun süresi dolmuş veya geçersiz. Lütfen tekrar talep edin."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if stored_code != code:
            return Response(
                {"detail": "Girilen sıfırlama kodu yanlış."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()
            cache.delete(cache_key)
            return Response(
                {"detail": "Şifreniz başarıyla sıfırlandı. Lütfen yeni şifrenizle giriş yapın."},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response({"detail": "Kullanıcı bulunamadı."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"PasswordResetCodeConfirmView: Şifre güncellenirken hata: {e}")
            return Response({"detail": "Şifre güncellenirken beklenmedik bir hata oluştu."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
