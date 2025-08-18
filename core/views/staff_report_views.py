# core/views/staff_report_views.py

from django.utils import timezone
from django.db.models import Count, Sum, Value, DecimalField, Q
from django.db.models.functions import Coalesce
from datetime import timedelta, datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
import logging
from decimal import Decimal

from ..models import Order, CustomUser, Payment, OrderItem, Business
from ..serializers import StaffPerformanceSerializer
from ..utils.order_helpers import get_user_business, PermissionKeys

logger = logging.getLogger(__name__)

class StaffPerformanceReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            business_for_report = get_user_business(user)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        if not business_for_report or user.user_type != 'business_owner':
            return Response(
                {"detail": "Bu raporu görüntülemek için işletme sahibi olmalısınız."},
                status=status.HTTP_403_FORBIDDEN
            )

        # ... (Tarih filtreleme mantığı aynı kalıyor) ...
        time_range = request.query_params.get('time_range', 'last_7_days')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        end_date_dt = timezone.now()
        start_date_dt = end_date_dt

        if start_date_str and end_date_str:
            try:
                start_date_dt = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.get_current_timezone())
                end_date_dt = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.get_current_timezone())
                if start_date_dt > end_date_dt:
                    return Response({"detail": "Başlangıç tarihi, bitiş tarihinden sonra olamaz."}, status=status.HTTP_400_BAD_REQUEST)
            except ValueError:
                return Response({"detail": "Geçersiz tarih formatı. YYYY-MM-DD formatını kullanın."}, status=status.HTTP_400_BAD_REQUEST)
        elif time_range == 'today':
            start_date_dt = end_date_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == 'this_week':
            start_date_dt = end_date_dt - timedelta(days=end_date_dt.weekday())
            start_date_dt = start_date_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == 'this_month':
            start_date_dt = end_date_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif time_range == 'last_7_days':
            start_date_dt = (end_date_dt - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == 'last_30_days':
            start_date_dt = (end_date_dt - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        else: # Varsayılan
            start_date_dt = (end_date_dt - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)


        all_staff_in_business = CustomUser.objects.filter(
            associated_business=business_for_report,
            user_type__in=['staff', 'kitchen_staff'],
            is_active=True
        ).prefetch_related('accessible_kds_screens')

        staff_members = [
            staff for staff in all_staff_in_business
            if PermissionKeys.TAKE_ORDERS in staff.staff_permissions or PermissionKeys.MANAGE_KDS in staff.staff_permissions
        ]

        staff_performance_data = []

        for staff in staff_members:
            orders_by_staff = Order.objects.filter(
                business=business_for_report,
                taken_by_staff=staff,
                is_paid=True,
                created_at__range=(start_date_dt, end_date_dt)
            )
            order_count = orders_by_staff.count()
            turnover_data = Payment.objects.filter(order__in=orders_by_staff).aggregate(
                total_turnover=Coalesce(Sum('amount'), Value(Decimal('0.00')), output_field=DecimalField())
            )
            total_turnover = turnover_data['total_turnover']

            prepared_item_count = OrderItem.objects.filter(
                item_prepared_by_staff=staff,
                order__created_at__range=(start_date_dt, end_date_dt)
            ).count()

            kds_names = list(staff.accessible_kds_screens.values_list('name', flat=True))

            staff_performance_data.append({
                'staff_id': staff.id,
                'username': staff.username,
                'first_name': staff.first_name,
                'last_name': staff.last_name,
                'order_count': order_count,
                'total_turnover': total_turnover,
                'prepared_item_count': prepared_item_count,
                'staff_permissions': staff.staff_permissions,
                'accessible_kds_names': kds_names,
                # --- YENİ VERİ EKLENDİ ---
                'profile_image_url': staff.profile_image_url,
            })
        
        serializer = StaffPerformanceSerializer(staff_performance_data, many=True)
        return Response(serializer.data)