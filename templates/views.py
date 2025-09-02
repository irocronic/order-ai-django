# templates/views.py

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import CategoryTemplate, MenuItemTemplate # MenuItemTemplate import edildi
from .serializers import CategoryTemplateSerializer, MenuItemTemplateSerializer # MenuItemTemplateSerializer import edildi

class CategoryTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    # ... mevcut kod ...

# === YENİ VIEWSET BAŞLANGICI ===
class MenuItemTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Kullanılabilir menü öğesi şablonlarını listeler.
    'category_template_id' query parametresi ile belirli bir kategoriye ait şablonları filtreler.
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
            
        return queryset
# === YENİ VIEWSET SONU ===