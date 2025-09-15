# core/views/guest_views.py

import json
import logging
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Prefetch, Q
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.urls import reverse

from ..models import (
    Business, Category, MenuItem, MenuItemVariant, Order, OrderItem, Table
)
from ..serializers import CategorySerializer, MenuItemSerializer, OrderSerializer

logger = logging.getLogger(__name__)

def guest_table_view(request, table_uuid):
    try:
        table = get_object_or_404(Table.objects.select_related('business'), uuid=table_uuid)
    except (ValueError, Table.DoesNotExist):
        raise Http404("Geçersiz masa kodu veya masa bulunamadı.")

    business = table.business
    menu_items_qs = MenuItem.objects.filter(
        business=business, is_active=True
    ).select_related(
        'category', 'represented_campaign'
    ).prefetch_related(
        'variants'
    )
    categories = Category.objects.filter(business=business)

    all_menu_items_data = MenuItemSerializer(menu_items_qs, many=True, context={'request': request}).data

    active_order = Order.objects.filter(
        table=table,
        business=business,
        customer__isnull=True,
        is_paid=False,
        credit_payment_details__isnull=True
    ).exclude(
        Q(status__in=[Order.STATUS_COMPLETED, Order.STATUS_CANCELLED, Order.STATUS_REJECTED])
    ).prefetch_related(
        Prefetch('order_items', queryset=OrderItem.objects.select_related('menu_item', 'variant').prefetch_related('extras__variant'))
    ).order_by('-created_at').first()

    active_order_data = None
    if active_order:
        active_order_data = OrderSerializer(active_order, context={'request': request}).data

    try:
        guest_order_api_url = reverse('core:guest_order_create_api', kwargs={'table_uuid': table.uuid})
    except Exception as e:
        logger.error(f"Hata: guest_order_create_api URL'si oluşturulamadı - {e}")
        guest_order_api_url = '#'

    context = {
        'view_type': 'table',
        'table': table,
        'business': business,
        'categories_from_django_view': categories,
        # --- DEĞİŞİKLİK: json.dumps kaldırıldı ---
        'all_menu_items_data_json': all_menu_items_data,
        'guest_order_api_url': guest_order_api_url,
        'csrf_token': request.COOKIES.get('csrftoken', ''),
        'active_order_data_json': active_order_data,
    }

    return render(request, 'core/guest_menu.html', context)


def guest_takeaway_view(request, order_uuid):
    try:
        order = get_object_or_404(
            Order.objects.select_related('business'),
            uuid=order_uuid,
            order_type='takeaway'
        )

        if order.status in [Order.STATUS_COMPLETED, Order.STATUS_CANCELLED, Order.STATUS_REJECTED] or order.is_paid:
            return render(request, 'error.html', {'error_message': 'Bu sipariş tamamlanmış veya iptal edilmiştir.'})

        business = order.business
        menu_items_qs = MenuItem.objects.filter(
            business=business, is_active=True
        ).select_related('category', 'represented_campaign').prefetch_related('variants')
        
        categories_qs = Category.objects.filter(business=business)

        all_menu_items_data = MenuItemSerializer(menu_items_qs, many=True, context={'request': request}).data
        active_order_data = OrderSerializer(order, context={'request': request}).data
        
        # Kategorileri serialize et
        categories_data = CategorySerializer(categories_qs, many=True, context={'request': request}).data
        
        try:
            guest_order_api_url = reverse('guest_takeaway_order_update_api', kwargs={'order_uuid': order.uuid})
        except Exception as e:
            logger.error(f"Hata: guest_takeaway_order_update_api URL'si oluşturulamadı - {e}")
            guest_order_api_url = '#'

        context = {
            'view_type': 'takeaway',
            'order': order,
            'business': business,
            # --- DEĞİŞİKLİK: json.dumps kaldırıldı ---
            'all_menu_items_data_json': all_menu_items_data,
            'categories_data_json': categories_data,
            'guest_order_api_url': guest_order_api_url,
            'csrf_token': request.COOKIES.get('csrftoken', ''),
            'active_order_data_json': active_order_data,
        }
        
        return render(request, 'core/takeaway_menu.html', context)
        
    except (ValueError, Order.DoesNotExist, Http404):
        return render(request, 'error.html', {'error_message': 'Geçersiz sipariş kodu veya bir hata oluştu.'})