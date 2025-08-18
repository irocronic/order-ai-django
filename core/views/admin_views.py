# core/views/admin_views.py
from rest_framework import viewsets, status
from rest_framework.permissions import IsAdminUser
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from ..models import Business
from ..serializers import (
    AdminBusinessOwnerSerializer,
    AdminStaffUserSerializer,
    UserActivationSerializer,
)

User = get_user_model()

class AdminUserManagementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin kullanıcısının, Flutter uygulamasındaki yönetici paneli üzerinden
    kullanıcıları yönetmesini sağlayan API endpoint'lerini barındırır.
    """
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        # Bu metodun içeriği aynı kalabilir, bir değişiklik gerekmiyor.
        if self.action == 'list_business_owners':
            return AdminBusinessOwnerSerializer
        elif self.action == 'list_staff_for_owner':
            return AdminStaffUserSerializer
        elif self.action == 'set_active_status':
            return UserActivationSerializer
        elif self.action == 'pending_approvals':
            return AdminBusinessOwnerSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=['get'], url_path='business-owners')
    def list_business_owners(self, request):
        users = User.objects.filter(user_type='business_owner').order_by('username')
        page = self.paginate_queryset(users)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(users, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='staff')
    def list_staff_for_owner(self, request, pk=None):
        owner = get_object_or_404(User, id=pk, user_type='business_owner')
        try:
            business = owner.owned_business
            staff_members = User.objects.filter(associated_business=business, user_type__in=['staff', 'kitchen_staff']).order_by('username')
            page = self.paginate_queryset(staff_members)
            if page is not None:
                serializer = self.get_serializer(page, many=True, context={'request': request})
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(staff_members, many=True, context={'request': request})
            return Response(serializer.data)
        except Business.DoesNotExist:
            return Response({"detail": "İşletme sahibi için bir işletme bulunamadı."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['patch'], url_path='set-active')
    def set_active_status(self, request, pk=None):
        user_to_manage = get_object_or_404(User, id=pk)
        if user_to_manage == request.user and user_to_manage.is_superuser:
            return Response({"detail": "Admin kendi aktiflik durumunu bu endpoint üzerinden değiştiremez."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            is_newly_active = serializer.validated_data['is_active']
            user_to_manage.is_active = is_newly_active
            user_to_manage.save(update_fields=['is_active'])
            
            if user_to_manage.user_type == 'business_owner':
                response_serializer = AdminBusinessOwnerSerializer(user_to_manage, context={'request': request})
            elif user_to_manage.user_type in ['staff', 'kitchen_staff']:
                response_serializer = AdminStaffUserSerializer(user_to_manage, context={'request': request})
            else:
                response_serializer = AdminBusinessOwnerSerializer(user_to_manage, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='delete-user')
    def delete_user_account(self, request, pk=None):
        user_to_delete = get_object_or_404(User, id=pk)
        if user_to_delete == request.user:
            return Response({"detail": "Admin kendi hesabını bu arayüzden silemez."}, status=status.HTTP_403_FORBIDDEN)
        
        user_type_display = user_to_delete.get_user_type_display()
        username_display = user_to_delete.username
        
        user_to_delete.delete()
        return Response(
            {"detail": f"'{username_display}' adlı '{user_type_display}' kullanıcısı başarıyla silindi."},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(detail=False, methods=['get'], url_path='pending-approvals')
    def pending_approvals(self, request):
        users = User.objects.filter(
            is_active=False,
            is_approved_by_admin=False,
            user_type__in=['customer', 'business_owner']
        ).order_by('-date_joined')
        
        page = self.paginate_queryset(users)
        if page is not None:
            serializer = AdminBusinessOwnerSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = AdminBusinessOwnerSerializer(users, many=True, context={'request': request})
        return Response(serializer.data)

    # --- ÖNEMLİ: GÜNCELLENEN FONKSİYON BURASI ---
    @action(detail=True, methods=['post'], url_path='approve')
    def approve_user(self, request, pk=None):
        """
        Belirli bir kullanıcıyı onaylar.
        Hem is_active hem de is_approved_by_admin alanlarını True yapar.
        """
        user_to_approve = get_object_or_404(User, id=pk)

        if user_to_approve.is_approved_by_admin:
            # Kullanıcı zaten onaylıysa sadece aktiflik durumunu kontrol et
            if user_to_approve.is_active:
                return Response({"detail": "Kullanıcı zaten onaylanmış ve aktif."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Onaylı ama pasif ise sadece aktif et
                user_to_approve.is_active = True
                user_to_approve.save(update_fields=['is_active'])
        else:
            # Hem onayı ver hem de aktifleştir
            user_to_approve.is_active = True
            user_to_approve.is_approved_by_admin = True
            user_to_approve.save(update_fields=['is_active', 'is_approved_by_admin'])
        
        # Onay sonrası güncellenmiş kullanıcı bilgisini döndür
        if user_to_approve.user_type == 'business_owner':
            response_serializer = AdminBusinessOwnerSerializer(user_to_approve, context={'request': request})
        elif user_to_approve.user_type == 'customer':
            response_serializer = AdminBusinessOwnerSerializer(user_to_approve, context={'request': request})
        else:
            response_serializer = AdminStaffUserSerializer(user_to_approve, context={'request': request})
            
        return Response(response_serializer.data, status=status.HTTP_200_OK)