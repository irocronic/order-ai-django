# core/views/places_views.py

import requests
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def google_places_autocomplete(request):
    """
    Google Places Autocomplete API için proxy endpoint
    """
    try:
        # Query parametrelerini al
        input_text = request.GET.get('input', '')
        session_token = request.GET.get('sessiontoken', '')
        language = request.GET.get('language', 'tr')
        components = request.GET.get('components', 'country:tr')
        
        print(f"🔍 Backend received search request: '{input_text}'")  # DEBUG
        
        if not input_text:
            return Response(
                {'error': 'Input parametresi gerekli'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Google Places API URL'ini oluştur
        google_api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', 'AIzaSyBAgXbA85EJfjSCc5BdQtEdH3wXJ1trb80')
        base_url = 'https://maps.googleapis.com/maps/api/place/autocomplete/json'
        
        params = {
            'input': input_text,
            'key': google_api_key,
            'sessiontoken': session_token,
            'language': language,
            'components': components,
        }
        
        print(f"🌐 Calling Google API with params: {params}")  # DEBUG
        
        # Google API'sine istek gönder
        response = requests.get(base_url, params=params, timeout=10)
        
        print(f"📡 Google API Response Status: {response.status_code}")  # DEBUG
        print(f"📡 Google API Response Body: {response.text[:500]}...")  # DEBUG (ilk 500 karakter)
        
        if response.status_code == 200:
            response_data = response.json()
            predictions_count = len(response_data.get('predictions', []))
            print(f"✅ Returning {predictions_count} predictions to frontend")  # DEBUG
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            logger.error(f"Google Places API Error: {response.status_code} - {response.text}")
            return Response(
                {'error': 'Google Places API hatası', 'details': response.text}, 
                status=status.HTTP_502_BAD_GATEWAY
            )
            
    except requests.exceptions.Timeout:
        logger.error("Google API timeout")
        return Response(
            {'error': 'Google API zaman aşımına uğradı'}, 
            status=status.HTTP_504_GATEWAY_TIMEOUT
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return Response(
            {'error': 'API isteği başarısız', 'details': str(e)}, 
            status=status.HTTP_502_BAD_GATEWAY
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return Response(
            {'error': 'Beklenmeyen hata oluştu', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def google_place_details(request):
    """
    Google Place Details API için proxy endpoint
    """
    try:
        place_id = request.GET.get('place_id', '')
        session_token = request.GET.get('sessiontoken', '')
        fields = request.GET.get('fields', 'geometry')
        
        print(f"📍 Backend received place details request: '{place_id}'")  # DEBUG
        
        if not place_id:
            return Response(
                {'error': 'place_id parametresi gerekli'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        google_api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', 'AIzaSyBAgXbA85EJfjSCc5BdQtEdH3wXJ1trb80')
        base_url = 'https://maps.googleapis.com/maps/api/place/details/json'
        
        params = {
            'place_id': place_id,
            'key': google_api_key,
            'sessiontoken': session_token,
            'fields': fields,
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        
        print(f"📡 Place Details Response Status: {response.status_code}")  # DEBUG
        print(f"📡 Place Details Response: {response.text[:300]}...")  # DEBUG
        
        if response.status_code == 200:
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            logger.error(f"Google Place Details API Error: {response.status_code} - {response.text}")
            return Response(
                {'error': 'Google Place Details API hatası', 'details': response.text}, 
                status=status.HTTP_502_BAD_GATEWAY
            )
            
    except requests.exceptions.Timeout:
        return Response(
            {'error': 'Google API zaman aşımına uğradı'}, 
            status=status.HTTP_504_GATEWAY_TIMEOUT
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return Response(
            {'error': 'API isteği başarısız', 'details': str(e)}, 
            status=status.HTTP_502_BAD_GATEWAY
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return Response(
            {'error': 'Beklenmeyen hata oluştu', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )