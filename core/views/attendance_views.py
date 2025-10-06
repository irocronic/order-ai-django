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
import logging

from core.models import CheckInLocation, QRCode, AttendanceRecord, Business, CustomUser

logger = logging.getLogger(__name__)

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

def validate_coordinates(latitude, longitude):
    """GPS koordinatlarının geçerliliğini kontrol eder"""
    try:
        lat = float(latitude)
        lon = float(longitude)
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (ValueError, TypeError):
        return False

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

    def _has_attendance_permission(self, user):
        """Kullanıcının giriş-çıkış işlemi yapma yetkisi var mı kontrol eder"""
        if user.user_type == 'business_owner':
            return True
        elif user.user_type in ['staff', 'kitchen_staff']:
            # Personelin manage_attendance yetkisi olup olmadığını kontrol et
            return getattr(user, 'staff_permissions', None) and 'manage_attendance' in user.staff_permissions
        return False

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

    def create_location(self, request):
        """Yeni check-in lokasyonu oluşturur - POST /attendance/locations/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        # Sadece işletme sahibi lokasyon oluşturabilir
        if request.user.user_type != 'business_owner':
            return Response({'error': 'Bu işlem için yetkiniz yok'}, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        
        # Gerekli alanların kontrolü
        required_fields = ['name', 'latitude', 'longitude']
        for field in required_fields:
            if field not in data:
                return Response({'error': f'Gerekli alan eksik: {field}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Koordinat validasyonu
        if not validate_coordinates(data['latitude'], data['longitude']):
            return Response({'error': 'Geçersiz koordinat değerleri'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Radius validasyonu
        radius_meters = data.get('radius_meters', 100.0)
        try:
            radius_meters = float(radius_meters)
            if radius_meters <= 0 or radius_meters > 10000:  # Max 10km
                return Response({'error': 'Yarıçap 0-10000 metre arasında olmalıdır'}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({'error': 'Geçersiz yarıçap değeri'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            location = CheckInLocation.objects.create(
                business=business,
                name=data['name'].strip(),
                latitude=float(data['latitude']),
                longitude=float(data['longitude']),
                radius_meters=radius_meters,
                is_active=data.get('is_active', True)
            )
            
            logger.info(f"Yeni check-in lokasyonu oluşturuldu: {location.name} (ID: {location.id})")
            
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
            
        except Exception as e:
            logger.error(f"Lokasyon oluşturma hatası: {str(e)}")
            return Response({'error': 'Lokasyon oluşturulurken bir hata oluştu'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        except ValueError:
            return Response({'error': 'Geçersiz lokasyon ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        data = request.data
        
        # Güncelleme işlemi
        if 'name' in data:
            if not data['name'].strip():
                return Response({'error': 'Lokasyon adı boş olamaz'}, status=status.HTTP_400_BAD_REQUEST)
            location.name = data['name'].strip()
        
        if 'latitude' in data or 'longitude' in data:
            new_lat = data.get('latitude', location.latitude)
            new_lon = data.get('longitude', location.longitude)
            if not validate_coordinates(new_lat, new_lon):
                return Response({'error': 'Geçersiz koordinat değerleri'}, status=status.HTTP_400_BAD_REQUEST)
            location.latitude = float(new_lat)
            location.longitude = float(new_lon)
        
        if 'radius_meters' in data:
            try:
                radius = float(data['radius_meters'])
                if radius <= 0 or radius > 10000:
                    return Response({'error': 'Yarıçap 0-10000 metre arasında olmalıdır'}, status=status.HTTP_400_BAD_REQUEST)
                location.radius_meters = radius
            except (ValueError, TypeError):
                return Response({'error': 'Geçersiz yarıçap değeri'}, status=status.HTTP_400_BAD_REQUEST)
        
        if 'is_active' in data:
            location.is_active = bool(data['is_active'])
        
        try:
            location.save()
            logger.info(f"Check-in lokasyonu güncellendi: {location.name} (ID: {location.id})")
        except Exception as e:
            logger.error(f"Lokasyon güncelleme hatası: {str(e)}")
            return Response({'error': 'Lokasyon güncellenirken bir hata oluştu'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
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
            
            # Aktif QR kodları olup olmadığını kontrol et - BU HATANIN SEBEBİ
            active_qr_count = QRCode.objects.filter(location=location, is_active=True).count()
            if active_qr_count > 0:
                # QR kodları pasif yap
                QRCode.objects.filter(location=location, is_active=True).update(is_active=False)
                logger.info(f"Lokasyon silinmeden önce {active_qr_count} aktif QR kod deaktif edildi")
            
            location_name = location.name
            location.delete()
            logger.info(f"Check-in lokasyonu silindi: {location_name} (ID: {pk})")
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except CheckInLocation.DoesNotExist:
            return Response({'error': 'Lokasyon bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({'error': 'Geçersiz lokasyon ID'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Lokasyon silme hatası: {str(e)}")
            return Response({'error': 'Lokasyon silinirken bir hata oluştu'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def generate_qr(self, request):
        """QR kod oluşturma - POST /attendance/qr-generate/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        # İzin kontrolü
        if not self._has_attendance_permission(request.user):
            return Response({'error': 'Bu işlem için yetkiniz yok'}, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        location_id = data.get('location_id')
        
        if not location_id:
            return Response({'error': 'location_id parametresi gerekli'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            location = CheckInLocation.objects.get(id=location_id, business=business)
            
            if not location.is_active:
                return Response({'error': 'Bu lokasyon aktif değil'}, status=status.HTTP_400_BAD_REQUEST)
                
        except CheckInLocation.DoesNotExist:
            return Response({'error': 'Lokasyon bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({'error': 'Geçersiz lokasyon ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Eski QR kodları deaktif et
            QRCode.objects.filter(location=location, is_active=True).update(is_active=False)
            
            # Yeni QR kod oluştur
            qr_code = QRCode.objects.create(
                location=location,
                expires_at=timezone.now() + timedelta(hours=24)  # 24 saat geçerli
            )
            
            logger.info(f"Yeni QR kod oluşturuldu: {location.name} için (QR ID: {qr_code.id})")
            
            return Response({
                'qr_data': str(qr_code.qr_data),
                'success': True,
                'expires_at': qr_code.expires_at.isoformat(),
                'location_name': location.name
            })
            
        except Exception as e:
            logger.error(f"QR kod oluşturma hatası: {str(e)}")
            return Response({'error': 'QR kod oluşturulurken bir hata oluştu'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def qr_checkin(self, request):
        """QR kod ile giriş-çıkış - POST /attendance/qr-checkin/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        # İzin kontrolü
        if not self._has_attendance_permission(request.user):
            return Response({'error': 'Bu işlem için yetkiniz yok'}, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        qr_data = data.get('qr_data')
        user_lat = data.get('latitude')
        user_lon = data.get('longitude')
        
        # Gerekli parametrelerin kontrolü
        if not qr_data:
            return Response({'error': 'qr_data parametresi gerekli'}, status=status.HTTP_400_BAD_REQUEST)
        
        if user_lat is None or user_lon is None:
            return Response({'error': 'latitude ve longitude parametreleri gerekli'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Koordinat validasyonu
        if not validate_coordinates(user_lat, user_lon):
            return Response({'error': 'Geçersiz koordinat değerleri'}, status=status.HTTP_400_BAD_REQUEST)
        
        user_lat = float(user_lat)
        user_lon = float(user_lon)
        
        # QR kodu doğrula - UUID formatını kontrol et
        try:
            qr_uuid = uuid.UUID(qr_data)
        except (ValueError, TypeError):
            return Response({'error': 'Geçersiz QR kod formatı'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            qr_obj = QRCode.objects.get(qr_data=qr_uuid, is_active=True)
            location = qr_obj.location
        except QRCode.DoesNotExist:
            return Response({'error': 'Geçersiz veya süresi dolmuş QR kod'}, status=status.HTTP_404_NOT_FOUND)
        
        # QR kodun geçerliliğini kontrol et
        if qr_obj.expires_at and qr_obj.expires_at < timezone.now():
            return Response({'error': 'QR kod süresi dolmuş'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Lokasyonun aktif olduğunu kontrol et
        if not location.is_active:
            return Response({'error': 'Bu lokasyon şu anda aktif değil'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Lokasyonun işletmeye ait olduğunu kontrol et
        if location.business != business:
            return Response({'error': 'Bu QR kod başka bir işletmeye ait'}, status=status.HTTP_403_FORBIDDEN)
        
        # Konum kontrolü
        is_valid = is_within_location(
            user_lat, user_lon,
            float(location.latitude), float(location.longitude),
            location.radius_meters
        )
        
        if not is_valid:
            distance = calculate_distance(
                user_lat, user_lon,
                float(location.latitude), float(location.longitude)
            )
            return Response({
                'error': f'Konum doğrulanamadı. Belirlenen alana {distance:.0f} metre uzaklıktasınız. Lütfen {location.radius_meters:.0f} metre içinde olduğunuzdan emin olun.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Aynı gün içinde çoklu giriş-çıkış kontrolü (opsiyonel)
        today = timezone.now().date()
        today_records_count = AttendanceRecord.objects.filter(
            user=request.user,
            business=business,
            timestamp__date=today
        ).count()
        
        if today_records_count >= 10:  # Günde max 10 giriş-çıkış
            return Response({
                'error': 'Günlük giriş-çıkış limit aşımı. Yöneticiniz ile iletişime geçin.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Son kaydı kontrol et (otomatik tip belirleme)
        last_record = AttendanceRecord.objects.filter(
            user=request.user, business=business
        ).order_by('-timestamp').first()
        
        if last_record and last_record.type == 'check_in':
            entry_type = 'check_out'
        else:
            entry_type = 'check_in'
        
        try:
            # Kayıt oluştur
            record = AttendanceRecord.objects.create(
                user=request.user,
                business=business,
                check_in_location=location,
                type=entry_type,
                latitude=user_lat,
                longitude=user_lon,
                qr_code_data=str(qr_uuid)
            )
            
            logger.info(f"Giriş-çıkış kaydı oluşturuldu: Kullanıcı {request.user.username}, Tip: {entry_type}, Lokasyon: {location.name}")
            
            return Response({
                'id': record.id,
                'user': record.user.id,
                'business': record.business.id,
                'type': record.type,
                'timestamp': record.timestamp.isoformat(),
                'latitude': float(record.latitude) if record.latitude else None,
                'longitude': float(record.longitude) if record.longitude else None,
                'check_in_location': record.check_in_location.id if record.check_in_location else None,
                'location_name': location.name,
                'notes': record.notes,
                'qr_code_data': record.qr_code_data,
                'is_manual_entry': record.is_manual_entry,
            })
            
        except Exception as e:
            logger.error(f"Giriş-çıkış kaydı oluşturma hatası: {str(e)}")
            return Response({'error': 'Giriş-çıkış kaydı oluşturulurken bir hata oluştu'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def current_status(self, request):
        """Mevcut giriş-çıkış durumu - GET /attendance/current-status/"""
        business = self._get_user_business(request.user)
        if not business:
            return Response({'error': 'İşletme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
        
        # Son kayıt
        last_record = AttendanceRecord.objects.filter(
            user=request.user, business=business
        ).order_by('-timestamp').first()
        
        # Son giriş ve çıkış kayıtlarını ayrı ayrı bul
        last_check_in = AttendanceRecord.objects.filter(
            user=request.user, business=business, type='check_in'
        ).order_by('-timestamp').first()
        
        last_check_out = AttendanceRecord.objects.filter(
            user=request.user, business=business, type='check_out'
        ).order_by('-timestamp').first()
        
        return Response({
            'is_checked_in': last_record.type == 'check_in' if last_record else False,
            'last_check_in': last_check_in.timestamp.isoformat() if last_check_in else None,
            'last_check_out': last_check_out.timestamp.isoformat() if last_check_out else None,
            'current_location': last_record.check_in_location.name if last_record and last_record.check_in_location else None,
        })

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
            except ValueError:
                return Response({'error': 'Geçersiz kullanıcı ID'}, status=status.HTTP_400_BAD_REQUEST)
        
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
        
        # Sayfalama
        limit = min(int(request.GET.get('limit', 100)), 500)  # Max 500 kayıt
        offset = int(request.GET.get('offset', 0))
        
        total_count = records_query.count()
        records = records_query.select_related('check_in_location').order_by('-timestamp')[offset:offset+limit]
        
        # Response hazırla - DÜZELTME: Burada liste formatı doğru
        records_data = []
        for record in records:
            records_data.append({
                'id': record.id,
                'user_id': record.user.id,  # DÜZELTME: user_id alanı eklendi
                'business': record.business.id,
                'type': record.type,
                'timestamp': record.timestamp.isoformat(),
                'latitude': float(record.latitude) if record.latitude else None,
                'longitude': float(record.longitude) if record.longitude else None,
                'check_in_location_id': record.check_in_location.id if record.check_in_location else None,  # DÜZELTME: field adı düzeltildi
                'location_name': record.check_in_location.name if record.check_in_location else None,
                'notes': record.notes,
                'qr_code_data': record.qr_code_data,
                'is_manual_entry': record.is_manual_entry,
            })
        
        # DÜZELTME: Response formatı düzeltildi
        return Response(records_data)


@api_view(['GET'])
def get_location_by_qr(request, qr_code):
    """QR koda göre lokasyon bilgisi getirme - GET /attendance/qr/<uuid>/"""
    try:
        # UUID formatını kontrol et
        qr_uuid = uuid.UUID(qr_code)
    except (ValueError, TypeError):
        return Response({'error': 'Geçersiz QR kod formatı'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        qr_obj = QRCode.objects.get(qr_data=qr_uuid, is_active=True)
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
            'is_active': location.is_active,
            'expires_at': qr_obj.expires_at.isoformat() if qr_obj.expires_at else None,
        })
    except QRCode.DoesNotExist:
        return Response({'error': 'Geçersiz veya süresi dolmuş QR kod'}, status=status.HTTP_404_NOT_FOUND)