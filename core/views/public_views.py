# core/views/ klasöründe public_views.py adında yeni bir dosya oluşturun

from django.shortcuts import render, get_object_or_404
from ..models import Business, MenuItem

def public_business_site_view(request, slug):
    """
    Verilen slug'a göre işletmenin herkese açık web sayfasını render eder.
    """
    business = get_object_or_404(Business, website_slug=slug, owner__is_active=True)
    
    # İşletmeye ait aktif menü öğelerini getir
    menu_items = MenuItem.objects.filter(
        business=business, 
        is_active=True, 
        is_campaign_bundle=False # Kampanya paketlerini göstermeyebiliriz
    ).select_related('category').prefetch_related('variants')

    context = {
        'business': business,
        'menu_items': menu_items,
    }
    
    return render(request, 'core/public_business_site.html', context)