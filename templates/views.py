# templates/views.py

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import CategoryTemplate
from .serializers import CategoryTemplateSerializer

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