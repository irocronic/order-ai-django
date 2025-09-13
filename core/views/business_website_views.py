# core/views/business_website_views.py

from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404, render
from django.http import Http404
from ..models import Business, BusinessWebsite, MenuItem, Category
from ..serializers.business_website_serializers import (
    BusinessWebsiteSerializer, 
    BusinessWebsiteUpdateSerializer,
    BusinessPublicSerializer
)

class BusinessWebsiteDetailView(generics.RetrieveUpdateAPIView):
    """
    İşletme sahibinin kendi web sitesi ayarları (görüntüle/güncelle)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        try:
            business = Business.objects.get(owner=self.request.user)
            website, _ = BusinessWebsite.objects.get_or_create(business=business)
            return website
        except Business.DoesNotExist:
            raise Http404("İşletme bulunamadı")

    def get_serializer_class(self):
        if self.request.method in ['PATCH', 'PUT']:
            return BusinessWebsiteUpdateSerializer
        return BusinessWebsiteSerializer

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def business_public_website_api(request, business_slug):
    """
    Herkese açık işletme web sitesi API'si (JSON)
    """
    try:
        business = get_object_or_404(Business.objects.select_related('website'), slug=business_slug)
        if not hasattr(business, 'website') or not business.website.is_active:
            return Response({'error': 'Web sitesi bulunamadı veya aktif değil'}, status=status.HTTP_404_NOT_FOUND)
        
        categories = Category.objects.filter(business=business, parent=None).order_by('name')
        menu_items = MenuItem.objects.filter(business=business, is_active=True).select_related('category')

        business_serializer = BusinessPublicSerializer(business)
        menu_data = {}
        for category in categories:
            category_items = [
                {
                    'id': item.id,
                    'name': item.name,
                    'description': item.description,
                    'price': float(item.price) if item.price else None,
                    'image': item.image,
                    'is_campaign_bundle': item.is_campaign_bundle
                }
                for item in menu_items.filter(category=category)
            ]
            if category_items:
                menu_data[category.name] = category_items

        response_data = {
            'business': business_serializer.data,
            'menu': menu_data,
            'meta': {
                'total_categories': len(menu_data),
                'total_items': len(menu_items)
            }
        }
        return Response(response_data)
    except Exception as e:
        return Response({'error': 'Bir hata oluştu', 'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def business_website_preview_api(request):
    """
    İşletme sahibinin kendi web sitesi önizlemesi için
    """
    try:
        business = Business.objects.get(owner=request.user)
        website, _ = BusinessWebsite.objects.get_or_create(business=business)
        serializer = BusinessWebsiteSerializer(website)
        return Response({
            'website': serializer.data,
            'business': {
                'name': business.name,
                'slug': business.slug,
            }
        })
    except Business.DoesNotExist:
        return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)

def business_website_view(request, business_slug):
    """İşletme web sitesi template view"""
    try:
        business = get_object_or_404(
            Business.objects.select_related('website'), 
            slug=business_slug
        )
        
        # Website aktif mi kontrol et
        if not hasattr(business, 'website') or not business.website.is_active:
            raise Http404("Web sitesi bulunamadı veya aktif değil")
        
        context = {
            'business': business,
            'website': business.website,
            'api_url': f'/api/public/business/{business_slug}/'
        }
        
        # Doğru şablon yolu: templates/business_website.html
        return render(request, 'business_website.html', context)
        
    except Exception as e:
        raise Http404("Web sitesi yüklenirken hata oluştu")