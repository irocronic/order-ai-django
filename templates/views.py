# templates/views.py

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import CategoryTemplate, MenuItemTemplate, VariantTemplate
from .serializers import CategoryTemplateSerializer, MenuItemTemplateSerializer, VariantTemplateSerializer

class CategoryTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Kullanılabilir kategori şablonlarını listeler.
    İsteğin 'Accept-Language' başlığına göre uygun dildeki şablonları döndürür.
    """
    serializer_class = CategoryTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Tarayıcıdan veya uygulamadan gelen dil tercihini al
        language_code = self.request.META.get('HTTP_ACCEPT_LANGUAGE', 'tr').split(',')[0].split('-')[0]
        
        # Önce istenen dildeki şablonları bul
        queryset = CategoryTemplate.objects.filter(language=language_code)
        
        # Eğer istenen dilde şablon yoksa, varsayılan olarak Türkçe (tr) şablonları döndür
        if not queryset.exists():
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
        queryset = MenuItemTemplate.objects.all()
        language_code = self.request.META.get('HTTP_ACCEPT_LANGUAGE', 'tr').split(',')[0].split('-')[0]
        
        # Önce dile göre filtrele
        queryset = queryset.filter(language=language_code)
        
        # Sonra kategori şablonu ID'sine göre filtrele (eğer sağlanmışsa)
        category_template_id = self.request.query_params.get('category_template_id')
        if category_template_id:
            queryset = queryset.filter(category_template_id=category_template_id)
            
        # Kategori şablonu ismine göre filtrele (eğer sağlanmışsa)
        category_template_name = self.request.query_params.get('category_template_name')
        if category_template_name:
            # category_template__name, ForeignKey ilişkisi üzerinden CategoryTemplate modelinin 'name' alanına erişir.
            queryset = queryset.filter(category_template__name=category_template_name)
            
        # Veritabanı sorgusunu optimize etmek için select_related ekliyoruz.
        return queryset.select_related('category_template')

# === YENİ VIEWSET ===
class VariantTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Kullanılabilir varyant şablonlarını listeler.
    'category_template_name' query parametresi ile filtreler.
    """
    serializer_class = VariantTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = VariantTemplate.objects.all()
        language_code = self.request.META.get('HTTP_ACCEPT_LANGUAGE', 'tr').split(',')[0].split('-')[0]
        
        # Önce dile göre filtrele
        queryset = queryset.filter(language=language_code)
        
        # Kategori şablonu ismine göre filtrele
        category_template_name = self.request.query_params.get('category_template_name')
        if category_template_name:
            queryset = queryset.filter(category_template__name=category_template_name)
            
        return queryset.select_related('category_template').order_by('display_order', 'name')