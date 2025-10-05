# core/views/attendance_views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
import math
from core.models import Location, Employee, AttendanceRecord, Company

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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_qr_code(request):
    """QR kod oluşturma"""
    if request.method == 'POST':
        data = request.data
        try:
            company = request.user.company
        except:
            return JsonResponse({'error': 'Şirket bulunamadı'}, status=404)
        
        location = Location.objects.create(
            company=company,
            name=data['name'],
            address=data['address'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            radius=data.get('radius', 100)
        )
        
        return JsonResponse({
            'qr_code': str(location.qr_code),
            'location_id': location.id
        })

@api_view(['GET'])
def get_location_by_qr(request, qr_code):
    """QR koda göre lokasyon bilgisi getirme"""
    try:
        location = Location.objects.get(qr_code=qr_code, is_active=True)
        return JsonResponse({
            'location_id': location.id,
            'name': location.name,
            'latitude': float(location.latitude),
            'longitude': float(location.longitude),
            'radius': location.radius
        })
    except Location.DoesNotExist:
        return JsonResponse({'error': 'Geçersiz QR kod'}, status=404)

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_attendance(request):
    """Giriş-çıkış kaydı oluşturma"""
    if request.method == 'POST':
        data = request.data if hasattr(request, 'data') else json.loads(request.body)
        
        try:
            location = Location.objects.get(qr_code=data['qr_code'])
            employee = Employee.objects.get(user=request.user)
            
            user_lat = float(data['latitude'])
            user_lon = float(data['longitude'])
            
            is_valid = is_within_location(
                user_lat, user_lon,
                float(location.latitude), float(location.longitude),
                location.radius
            )
            
            if not is_valid:
                return JsonResponse({
                    'error': 'Konum doğrulanamadı. Lütfen belirlenen alan içinde olduğunuzdan emin olun.'
                }, status=400)
            
            # Son kaydı kontrol et
            last_record = AttendanceRecord.objects.filter(
                employee=employee
            ).order_by('-timestamp').first()
            
            # Otomatik entry_type belirleme
            if last_record and last_record.entry_type == 'IN':
                entry_type = 'OUT'
            else:
                entry_type = 'IN'
            
            record = AttendanceRecord.objects.create(
                employee=employee,
                location=location,
                entry_type=entry_type,
                gps_latitude=user_lat,
                gps_longitude=user_lon,
                is_valid_location=is_valid
            )
            
            return JsonResponse({
                'success': True,
                'entry_type': entry_type,
                'timestamp': record.timestamp.isoformat(),
                'location_name': location.name
            })
            
        except Location.DoesNotExist:
            return JsonResponse({'error': 'Geçersiz lokasyon'}, status=404)
        except Employee.DoesNotExist:
            return JsonResponse({'error': 'Çalışan bulunamadı'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_status(request):
    """Çalışanların gerçek zamanlı durumunu getirme"""
    try:
        company = request.user.company
        employees = Employee.objects.filter(company=company, is_active=True)
        
        employee_statuses = []
        for employee in employees:
            last_record = AttendanceRecord.objects.filter(
                employee=employee
            ).order_by('-timestamp').first()
            
            status = {
                'employee_id': employee.id,
                'name': f"{employee.user.first_name} {employee.user.last_name}",
                'is_at_work': last_record.entry_type == 'IN' if last_record else False,
                'last_action': last_record.timestamp.isoformat() if last_record else None,
                'location': last_record.location.name if last_record else None
            }
            employee_statuses.append(status)
            
        return JsonResponse({'employees': employee_statuses})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_attendance_history(request):
    """Çalışan giriş-çıkış geçmişini getirme"""
    try:
        employee = Employee.objects.get(user=request.user)
        
        # Query parametrelerini al
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        records = AttendanceRecord.objects.filter(employee=employee)
        
        if start_date:
            records = records.filter(timestamp__gte=start_date)
        if end_date:
            records = records.filter(timestamp__lte=end_date)
            
        records = records.order_by('-timestamp')
        
        history_data = []
        for record in records:
            history_data.append({
                'id': record.id,
                'entry_type': record.entry_type,
                'timestamp': record.timestamp.isoformat(),
                'location_name': record.location.name,
                'notes': record.notes,
                'is_valid_location': record.is_valid_location
            })
        
        return JsonResponse({'history': history_data})
        
    except Employee.DoesNotExist:
        return JsonResponse({'error': 'Çalışan bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)