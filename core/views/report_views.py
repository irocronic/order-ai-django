# core/views/report_views.py

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Sum, Count, Value, CharField, Func, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth, TruncDay, TruncHour, Coalesce
from datetime import timedelta, datetime

from ..models import Business, Payment, Order, OrderItem, MenuItem, CustomUser as User
# YENİ: Yeni serializer import edildi
from ..serializers import StaffPerformanceSerializer, DetailedSaleItemSerializer 
from ..utils.order_helpers import get_user_business, PermissionKeys

class ReportView(APIView):
    # Bu sınıfın içeriğinde bir değişiklik yok, olduğu gibi kalıyor...
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            business_for_report = get_user_business(user)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        if not business_for_report:
            return Response({"detail": "Raporları görüntülemek için yetkili bir işletmeniz bulunmuyor."}, status=status.HTTP_403_FORBIDDEN)

        if user.user_type == 'staff':
            if PermissionKeys.VIEW_REPORTS not in user.staff_permissions:
                return Response({"detail": "Raporları görüntüleme yetkiniz yok."}, status=status.HTTP_403_FORBIDDEN)

        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        time_range_filter = request.query_params.get('time_range', 'day')

        start_date = None
        end_date = None
        effective_time_range = time_range_filter

        current_tz = timezone.get_current_timezone()

        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                start_date = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), current_tz)
                end_date = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), current_tz)
                if start_date > end_date:
                    return Response({"detail": "Başlangıç tarihi, bitiş tarihinden sonra olamaz."}, status=status.HTTP_400_BAD_REQUEST)
                effective_time_range = 'custom'
            except ValueError:
                return Response({"detail": "Geçersiz tarih formatı. YYYY-MM-DD formatını kullanın."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            now = timezone.now()
            if time_range_filter == 'day':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            elif time_range_filter == 'week':
                start_of_week = now - timedelta(days=now.weekday())
                start_date = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_week = start_of_week + timedelta(days=6)
                end_date = end_of_week.replace(hour=23, minute=59, second=59, microsecond=999999)
            elif time_range_filter == 'month':
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                next_month = (start_date.replace(day=28) + timedelta(days=4))
                end_of_month = next_month - timedelta(days=next_month.day)
                end_date = end_of_month.replace(hour=23, minute=59, second=59, microsecond=999999)
            elif time_range_filter == 'year':
                start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
            else:
                time_range_filter = 'day'
                effective_time_range = 'day'
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        payments_in_range = Payment.objects.filter(
            order__business=business_for_report,
            payment_date__gte=start_date,
            payment_date__lte=end_date
        )
        orders_in_range = Order.objects.filter(
            business=business_for_report,
            created_at__gte=start_date,
            created_at__lte=end_date,
            is_paid=True
        )
        order_items_in_range = OrderItem.objects.filter(
            order__business=business_for_report,
            order__is_paid=True,
            order__created_at__gte=start_date,
            order__created_at__lte=end_date
        )

        total_turnover = payments_in_range.aggregate(total=Sum('amount'))['total'] or 0
        total_orders = orders_in_range.count()

        selling_stats = order_items_in_range.values(
            'menu_item__id',
            'menu_item__name'
        ).annotate(
            total_qty=Sum('quantity')
        ).filter(total_qty__gt=0).order_by('-total_qty')

        best_selling_item_data = selling_stats.first()
        best_selling_item = {
            'id': best_selling_item_data['menu_item__id'],
            'name': best_selling_item_data['menu_item__name'],
            'total_sold': best_selling_item_data['total_qty']
        } if best_selling_item_data else None

        least_selling_item_data = selling_stats.last()
        least_selling_item = {
            'id': least_selling_item_data['menu_item__id'],
            'name': least_selling_item_data['menu_item__name'],
            'total_sold': least_selling_item_data['total_qty']
        } if least_selling_item_data and best_selling_item_data != least_selling_item_data else None

        daily_turnover_for_chart = []
        weekly_turnover_for_chart = []
        monthly_turnover_for_chart = []

        if effective_time_range == 'day':
            daily_turnover_for_chart = list(
                payments_in_range.annotate(
                    hour=TruncHour('payment_date', tzinfo=current_tz)
                ).values('hour').annotate(
                    turnover=Sum('amount')
                ).order_by('hour').values('hour', 'turnover')
            )
            for item in daily_turnover_for_chart:
                if isinstance(item['hour'], datetime):
                    item['hour_str'] = item['hour'].strftime('%H:00')
                else:
                    item['hour_str'] = str(item['hour'])

        elif effective_time_range == 'week' or (effective_time_range == 'custom' and (end_date - start_date).days <= 30):
            weekly_turnover_for_chart = list(
                payments_in_range.annotate(
                    day=TruncDay('payment_date', tzinfo=current_tz)
                ).values('day').annotate(
                    turnover=Sum('amount')
                ).order_by('day').values('day', 'turnover')
            )
            for item in weekly_turnover_for_chart:
                if isinstance(item['day'], datetime):
                    item['day_str'] = item['day'].strftime('%d %b')
                else:
                    item['day_str'] = str(item['day'])

        elif effective_time_range == 'month' or effective_time_range == 'year' or \
             (effective_time_range == 'custom' and (end_date - start_date).days > 30):
            monthly_turnover_for_chart = list(
                payments_in_range.annotate(
                    month_year=TruncMonth('payment_date', tzinfo=current_tz)
                ).values('month_year').annotate(
                    turnover=Sum('amount')
                ).order_by('month_year').values('month_year', 'turnover')
            )
            for item in monthly_turnover_for_chart:
                if isinstance(item['month_year'], datetime):
                    item['month_year_str'] = item['month_year'].strftime('%Y-%m')
                else:
                    item['month_year_str'] = str(item['month_year'])

        return Response({
            "total_turnover": total_turnover,
            "total_orders": total_orders,
            "best_selling_item": best_selling_item,
            "least_selling_item": least_selling_item,
            "start_date": start_date.strftime("%Y-%m-%d") if start_date else None,
            "end_date": end_date.strftime("%Y-%m-%d") if end_date else None,
            "time_range_selected": effective_time_range,
            "daily_turnover_for_chart": daily_turnover_for_chart,
            "weekly_turnover_for_chart": weekly_turnover_for_chart,
            "monthly_turnover_for_chart": monthly_turnover_for_chart,
        })


# ==================== YENİ EKLENEN BÖLÜM ====================

class DetailedSalesReportView(APIView):
    """
    Excel'e aktarmak için detaylı satış raporu sunar.
    Her bir satır, satılmış bir ürün kalemini temsil eder.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = DetailedSaleItemSerializer

    def get(self, request):
        user = request.user
        try:
            business_for_report = get_user_business(user)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        if not business_for_report:
            return Response({"detail": "Raporları görüntülemek için yetkili bir işletmeniz bulunmuyor."}, status=status.HTTP_403_FORBIDDEN)

        if user.user_type == 'staff' and PermissionKeys.VIEW_REPORTS not in user.staff_permissions:
            return Response({"detail": "Raporları görüntüleme yetkiniz yok."}, status=status.HTTP_403_FORBIDDEN)

        # Tarih aralığı belirleme mantığı ReportView ile aynı
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        time_range_filter = request.query_params.get('time_range', 'day')

        start_date, end_date = None, None
        current_tz = timezone.get_current_timezone()

        if start_date_str and end_date_str:
            try:
                start_date = timezone.make_aware(datetime.strptime(start_date_str, "%Y-%m-%d"), current_tz)
                end_date = timezone.make_aware(datetime.combine(datetime.strptime(end_date_str, "%Y-%m-%d"), datetime.max.time()), current_tz)
            except ValueError:
                return Response({"detail": "Geçersiz tarih formatı."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            now = timezone.now()
            if time_range_filter == 'day':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif time_range_filter == 'week':
                start_date = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            elif time_range_filter == 'month':
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            elif time_range_filter == 'year':
                start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now

        if start_date is None:
             start_date = (timezone.now() - timedelta(days=365*5)) # Hata olmaması için çok eski bir tarih
        
        # Detaylı rapor için veritabanı sorgusu
        sales_data = OrderItem.objects.filter(
            order__business=business_for_report,
            order__is_paid=True,
            order__created_at__range=(start_date, end_date)
        ).select_related(
            'order', 'order__table', 'menu_item', 'variant'
        ).annotate(
            line_total=ExpressionWrapper(F('price') * F('quantity'), output_field=DecimalField())
        ).values(
            'order__id', 'order__created_at', 'order__order_type', 'order__table__table_number',
            'order__customer_name', 'menu_item__name', 'variant__name', 'quantity',
            'price', 'line_total'
        ).order_by('order__created_at')

        # Alan isimlerini Flutter tarafının beklediği şekilde yeniden adlandır
        renamed_data = [
            {
                'order_id': item['order__id'],
                'created_at': item['order__created_at'],
                'order_type': item['order__order_type'],
                'table_number': item['order__table__table_number'],
                'customer_name': item['order__customer_name'],
                'item_name': item['menu_item__name'],
                'variant_name': item['variant__name'],
                'quantity': item['quantity'],
                'unit_price': item['price'],
                'line_total': item['line_total'],
            }
            for item in sales_data
        ]
        
        serializer = self.serializer_class(renamed_data, many=True)
        return Response(serializer.data)

# ==================== YENİ EKLENEN BÖLÜM SONU ====================