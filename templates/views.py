from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import CategoryTemplate, MenuItemTemplate, VariantTemplate
from .serializers import CategoryTemplateSerializer, MenuItemTemplateSerializer, VariantTemplateSerializer

def get_language_from_request(request):
    """Helper function to get language code from request headers."""
    # 'tr' veya 'en' gibi iki harfli kodları alır.
    lang_header = request.META.get('HTTP_ACCEPT_LANGUAGE', 'tr')
    return lang_header.split(',')[0].split('-')[0].lower()

class CategoryTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Kullanılabilir kategori şablonlarını listeler.
    İsteğin 'Accept-Language' başlığına göre uygun dildeki şablonları döndürür.
    """
    serializer_class = CategoryTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        language_code = get_language_from_request(self.request)
        
        # İstenen dildeki şablonları sorgula
        queryset = CategoryTemplate.objects.filter(language=language_code)
        
        # Eğer sonuç yoksa ve istenen dil varsayılan (Türkçe) değilse, Türkçe'ye geri dön
        if not queryset.exists() and language_code != 'tr':
            return CategoryTemplate.objects.filter(language='tr')
            
        return queryset

class MenuItemTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Kullanılabilir menü öğesi şablonlarını listeler.
    'category_template_id' veya 'category_template_name' query parametresi ile filtreler.
    """
    serializer_class = MenuItemTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        language_code = get_language_from_request(self.request)
        
        # İstenen dildeki şablonları sorgula
        queryset = MenuItemTemplate.objects.filter(language=language_code)
        
        # Kategoriye göre filtreleme
        category_template_id = self.request.query_params.get('category_template_id')
        if category_template_id:
            queryset = queryset.filter(category_template_id=category_template_id)
            
        category_template_name = self.request.query_params.get('category_template_name')
        if category_template_name:
            queryset = queryset.filter(category_template__name=category_template_name)

        # Eğer sonuç yoksa ve varsayılan dil değilse, Türkçe'ye geri dön ve aynı filtreyi uygula
        if not queryset.exists() and language_code != 'tr':
            fallback_queryset = MenuItemTemplate.objects.filter(language='tr')
            if category_template_id:
                # Kategori ID'si ile gelen isteklerde fallback yapmak zordur,
                # çünkü ID'ler dile göre değişir. Bu durumda boş dönmek veya isimle filtrelemek daha mantıklıdır.
                # Mevcut yapıda ID'ye göre fallback yapmadan devam ediyoruz.
                pass
            if category_template_name:
                 fallback_queryset = fallback_queryset.filter(category_template__name=category_template_name)
            return fallback_queryset.select_related('category_template')

        return queryset.select_related('category_template')

class VariantTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Kullanılabilir varyant şablonlarını listeler.
    'category_template_name' query parametresi ile filtreler.
    """
    serializer_class = VariantTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        language_code = get_language_from_request(self.request)
        
        queryset = VariantTemplate.objects.filter(language=language_code)
        
        category_template_name = self.request.query_params.get('category_template_name')
        if category_template_name:
            queryset = queryset.filter(category_template__name=category_template_name)
            
        if not queryset.exists() and language_code != 'tr':
            fallback_queryset = VariantTemplate.objects.filter(language='tr')
            if category_template_name:
                fallback_queryset = fallback_queryset.filter(category_template__name=category_template_name)
            return fallback_queryset.select_related('category_template').order_by('display_order', 'name')
            
        return queryset.select_related('category_template').order_by('display_order', 'name')