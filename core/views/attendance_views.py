# core/views/attendance_views.py
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import datetime, timedelta
import math
import uuid

from core.models import CheckInLocation, QRCode, AttendanceRecord, Business, CustomUser

def calculate_distance(lat1, lon1, lat2, lon2):
    """İki GPS koordinatı arasındaki mesafeyi metre cinsinden hesaplar"""
    R = 6371000  # Dünya'nın yarıçapı (metre)
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * 
         math.sin(delta_lon/2) * math.sin(delta_lon/2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance

def is_within_location(user_lat, user_lon, location_lat, location_lon, radius):
    """Kullanıcının belirlenen radius içinde olup olmadığını kontrol eder"""
    distance = calculate_distance(user_lat, user_lon, location_lat, location_lon)
    return distance <= radius

class AttendanceViewSet(viewsets.ViewSet):
    """
    Personel giriş-çıkış işlemleri için ViewSet
    """
    permission_classes = [IsAuthenticated]

    def _get_user_business(self, user):
        """Kullanıcının işletmesini döndürür"""
        if user.user_type == 'business_owner':
            return getattr(user, 'owned_business', None)
        elif user.user_type in ['staff', 'kitchen_staff']:
            return user.associated_business
        return None

    @action(detail=False, methods=['get'])
    def locations(self, request):
        """Check-in lokasyonlarını listeler - GET /attendance/locations/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        locations = CheckInLocation.objects.filter(business=business)
        locations_data = []
        
        for location in locations:
            locations_data.append({
                'id': location.id,
                'business': location.business.id,
                'name': location.name,
                'latitude': float(location.latitude),
                'longitude': float(location.longitude),
                'radius_meters': location.radius_meters,
                'is_active': location.is_active,
                'created_at': location.created_at.isoformat() if location.created_at else None,
                'updated_at': location.updated_at.isoformat() if location.updated_at else None,
            })
        
        return Response(locations_data)

    @action(detail=False, methods=['post'])
    def create_location(self, request):
        """Yeni check-in lokasyonu oluşturur - POST /attendance/locations/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        # Sadece işletme sahibi lokasyon oluşturabilir
        if request.user.user_type != 'business_owner':
            return Response({'error': 'Bu işlem için yetkiniz yok'}, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        try:
            location = CheckInLocation.objects.create(
                business=business,
                name=data['name'],
                latitude=data['latitude'],
                longitude=data['longitude'],
                radius_meters=data.get('radius_meters', 100.0),
                is_active=data.get('is_active', True)
            )
            
            return Response({
                'id': location.id,
                'business': location.business.id,
                'name': location.name,
                'latitude': float(location.latitude),
                'longitude': float(location.longitude),
                'radius_meters': location.radius_meters,
                'is_active': location.is_active,
                'created_at': location.created_at.isoformat(),
                'updated_at': location.updated_at.isoformat(),
            }, status=status.HTTP_201_CREATED)
            
        except KeyError as e:
            return Response({'error': f'Gerekli alan eksik: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['put'])
    def update_location(self, request, pk=None):
        """Check-in lokasyonunu günceller - PUT /attendance/locations/{id}/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        # Sadece işletme sahibi lokasyon güncelleyebilir
        if request.user.user_type != 'business_owner':
            return Response({'error': 'Bu işlem için yetkiniz yok'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            location = CheckInLocation.objects.get(id=pk, business=business)
        except CheckInLocation.DoesNotExist:
            return Response({'error': 'Lokasyon bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        data = request.data
        
        # Güncelleme işlemi
        if 'name' in data:
            location.name = data['name']
        if 'latitude' in data:
            location.latitude = data['latitude']
        if 'longitude' in data:
            location.longitude = data['longitude']
        if 'radius_meters' in data:
            location.radius_meters = data['radius_meters']
        if 'is_active' in data:
            location.is_active = data['is_active']
        
        location.save()
        
        return Response({
            'id': location.id,
            'business': location.business.id,
            'name': location.name,
            'latitude': float(location.latitude),
            'longitude': float(location.longitude),
            'radius_meters': location.radius_meters,
            'is_active': location.is_active,
            'updated_at': location.updated_at.isoformat(),
        })

    @action(detail=True, methods=['delete'])
    def delete_location(self, request, pk=None):
        """Check-in lokasyonunu siler - DELETE /attendance/locations/{id}/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        # Sadece işletme sahibi lokasyon silebilir
        if request.user.user_type != 'business_owner':
            return Response({'error': 'Bu işlem için yetkiniz yok'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            location = CheckInLocation.objects.get(id=pk, business=business)
            location.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except CheckInLocation.DoesNotExist:
            return Response({'error': 'Lokasyon bulunamadı'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def generate_qr(self, request):
        """QR kod oluşturma - POST /attendance/qr-generate/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        data = request.data
        location_id = data.get('location_id')
        
        try:
            location = CheckInLocation.objects.get(id=location_id, business=business)
        except CheckInLocation.DoesNotExist:
            return Response({'error': 'Lokasyon bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        # QR kod oluştur
        qr_code = QRCode.objects.create(
            location=location,
            expires_at=timezone.now() + timedelta(hours=24)  # 24 saat geçerli
        )
        
        return Response({
            'qr_data': str(qr_code.qr_data),
            'success': True
        })

    @action(detail=False, methods=['post'])
    def qr_checkin(self, request):
        """QR kod ile giriş-çıkış - POST /attendance/qr-checkin/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        data = request.data
        qr_data = data.get('qr_data')
        user_lat = float(data.get('latitude', 0))
        user_lon = float(data.get('longitude', 0))
        
        # QR kodu doğrula
        try:
            qr_obj = QRCode.objects.get(qr_data=qr_data, is_active=True)
            location = qr_obj.location
        except QRCode.DoesNotExist:
            return Response({'error': 'Geçersiz QR kod'}, status=status.HTTP_404_NOT_FOUND)
        
        # QR kodun geçerliliğini kontrol et
        if qr_obj.expires_at and qr_obj.expires_at < timezone.now():
            return Response({'error': 'QR kod süresi dolmuş'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Konum kontrolü
        is_valid = is_within_location(
            user_lat, user_lon,
            float(location.latitude), float(location.longitude),
            location.radius_meters
        )
        
        if not is_valid:
            return Response({
                'error': 'Konum doğrulanamadı. Lütfen belirlenen alan içinde olduğunuzdan emin olun.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Son kaydı kontrol et (otomatik tip belirleme)
        last_record = AttendanceRecord.objects.filter(
            user=request.user, business=business
        ).order_by('-timestamp').first()
        
        if last_record and last_record.type == 'check_in':
            entry_type = 'check_out'
        else:
            entry_type = 'check_in'
        
        # Kayıt oluştur
        record = AttendanceRecord.objects.create(
            user=request.user,
            business=business,
            check_in_location=location,
            type=entry_type,
            latitude=user_lat,
            longitude=user_lon,
            qr_code_data=qr_data
        )
        
        return Response({
            'id': record.id,
            'user': record.user.id,
            'business': record.business.id,
            'type': record.type,
            'timestamp': record.timestamp.isoformat(),
            'latitude': float(record.latitude) if record.latitude else None,
            'longitude': float(record.longitude) if record.longitude else None,
            'check_in_location': record.check_in_location.id if record.check_in_location else None,
            'notes': record.notes,
            'qr_code_data': record.qr_code_data,
            'is_manual_entry': record.is_manual_entry,
        })

    @action(detail=False, methods=['get'])
    def current_status(self, request):
        """Mevcut giriş-çıkış durumu - GET /attendance/current-status/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        # Son kayıt
        last_record = AttendanceRecord.objects.filter(
            user=request.user, business=business
        ).order_by('-timestamp').first()
        
        return Response({
            'is_checked_in': last_record.type == 'check_in' if last_record else False,
            'last_check_in': last_record.timestamp.isoformat() if last_record and last_record.type == 'check_in' else None,
            'last_check_out': last_record.timestamp.isoformat() if last_record and last_record.type == 'check_out' else None,
        })

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Giriş-çıkış geçmişi - GET /attendance/history/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        user_id = request.GET.get('user_id')
        
        # Sorgu oluştur
        query_user = request.user
        if user_id and request.user.user_type == 'business_owner':
            # İş sahibi diğer personelin kayıtlarını görebilir
            try:
                query_user = CustomUser.objects.get(id=user_id, associated_business=business)
            except CustomUser.DoesNotExist:
                return Response({'error': 'Kullanıcı bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        records_query = AttendanceRecord.objects.filter(user=query_user, business=business)
        
        # Tarih filtreleri
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                records_query = records_query.filter(timestamp__gte=start_datetime)
            except ValueError:
                return Response({'error': 'Geçersiz başlangıç tarihi formatı (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)
        
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                records_query = records_query.filter(timestamp__lt=end_datetime)
            except ValueError:
                return Response({'error': 'Geçersiz bitiş tarihi formatı (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)
        
        records = records_query.order_by('-timestamp')[:100]  # Son 100 kayıt
        
        # Response hazırla
        records_data = []
        for record in records:
            records_data.append({
                'id': record.id,
                'user': record.user.id,
                'business': record.business.id,
                'type': record.type,
                'timestamp': record.timestamp.isoformat(),
                'latitude': float(record.latitude) if record.latitude else None,
                'longitude': float(record.longitude) if record.longitude else None,
                'check_in_location': record.check_in_location.id if record.check_in_location else None,
                'notes': record.notes,
                'qr_code_data': record.qr_code_data,
                'is_manual_entry': record.is_manual_entry,
            })
        
        return Response(records_data)


@api_view(['GET'])
def get_location_by_qr(request, qr_code):
    """QR koda göre lokasyon bilgisi getirme - GET /attendance/qr/<uuid>/"""
    try:
        qr_obj = QRCode.objects.get(qr_data=qr_code, is_active=True)
        location = qr_obj.location
        
        # QR kodun geçerliliğini kontrol et
        if qr_obj.expires_at and qr_obj.expires_at < timezone.now():
            return Response({'error': 'QR kod süresi dolmuş'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'location_id': location.id,
            'name': location.name,
            'latitude': float(location.latitude),
            'longitude': float(location.longitude),
            'radius': location.radius_meters,
        })
    except QRCode.DoesNotExist:
        return Response({'error': 'Geçersiz QR kod'}, status=status.HTTP_404_NOT_FOUND)


# Eski function-based view'ları koruma amaçlı (geçici)
# Bu fonksiyonlar gelecekte kaldırılacak
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_qr_code(request):
    """DEPRECATED: AttendanceViewSet.generate_qr kullanın"""
    viewset = AttendanceViewSet()
    return viewset.generate_qr(request)

@api_view(['POST'])
@permission_classes([IsAuthenticated])  # DÜZELTME: IsAuthenticated olarak değiştirildi
def record_attendance(request):
    """DEPRECATED: AttendanceViewSet.qr_checkin kullanın"""
    viewset = AttendanceViewSet()
    return viewset.qr_checkin(request)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_status(request):
    """DEPRECATED: AttendanceViewSet.current_status kullanın"""
    viewset = AttendanceViewSet()
    return viewset.current_status(request)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_attendance_history(request):
    """DEPRECATED: AttendanceViewSet.history kullanın"""
    viewset = AttendanceViewSet()
    return viewset.history(request)