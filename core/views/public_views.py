# core/views/public_views.py

import logging
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from ..models import Business, MenuItem

# Logger oluştur
logger = logging.getLogger(__name__)

def public_business_site_view(request, slug):
    """
    Verilen slug'a göre işletmenin herkese açık web sayfasını render eder.
    """
    logger.info(f"🔍 Public site view çağrıldı - slug: '{slug}', IP: {request.META.get('REMOTE_ADDR')}")
    logger.info(f"📍 Request path: {request.path}")
    logger.info(f"🌐 Request method: {request.method}")
    
    try:
        # İşletmeyi bul
        logger.info(f"🔎 İşletme aranıyor - website_slug='{slug}', owner__is_active=True")
        business = get_object_or_404(Business, website_slug=slug, owner__is_active=True)
        logger.info(f"✅ İşletme bulundu: '{business.name}' (ID: {business.id})")
        
        # İşletmeye ait aktif menü öğelerini getir
        menu_items = MenuItem.objects.filter(
            business=business, 
            is_active=True, 
            is_campaign_bundle=False
        ).select_related('category').prefetch_related('variants')
        
        logger.info(f"📋 {menu_items.count()} menü öğesi bulundu")

        context = {
            'business': business,
            'menu_items': menu_items,
        }
        
        logger.info(f"🎨 Template render ediliyor: 'core/public_business_site.html'")
        response = render(request, 'core/public_business_site.html', context)
        logger.info(f"✅ Template başarıyla render edildi")
        return response
        
    except Business.DoesNotExist:
        logger.error(f"❌ İşletme bulunamadı - slug: '{slug}'")
        logger.error(f"🔍 Veritabanında mevcut işletmeler kontrol ediliyor...")
        
        # Mevcut işletmeleri logla
        all_businesses = Business.objects.all()
        logger.error(f"📊 Toplam {all_businesses.count()} işletme mevcut:")
        for biz in all_businesses:
            logger.error(f"   - ID: {biz.id}, Name: '{biz.name}', Slug: '{biz.website_slug}', Owner Active: {biz.owner.is_active}")
        
        return HttpResponse(f"İşletme bulunamadı: '{slug}'", status=404)
        
    except Exception as e:
        logger.error(f"💥 Beklenmeyen hata: {str(e)}")
        logger.error(f"💥 Hata tipi: {type(e).__name__}")
        import traceback
        logger.error(f"💥 Traceback: {traceback.format_exc()}")
        return HttpResponse(f"Hata: {str(e)}", status=500)