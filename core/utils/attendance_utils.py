from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, timedelta
import json
import math
from .models import Location, Employee, AttendanceRecord, Company
from .utils import calculate_distance, is_within_location

@login_required
def generate_qr_code(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Company kontrolü
            try:
                company = request.user.company
            except AttributeError:
                return JsonResponse({'error': 'Şirket bilgisi bulunamadı'}, status=400)
            
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
                'location_id': location.id,
                'success': True
            })
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Geçersiz istek metodu'}, status=405)

def get_location_by_qr(request, qr_code):
    try:
        location = Location.objects.get(qr_code=qr_code, is_active=True)
        return JsonResponse({
            'location_id': location.id,
            'name': location.name,
            'latitude': float(location.latitude),
            'longitude': float(location.longitude),
            'radius': location.radius,
            'address': location.address
        })
    except Location.DoesNotExist:
        return JsonResponse({'error': 'Geçersiz QR kod'}, status=404)

@csrf_exempt
def record_attendance(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Kullanıcı giriş kontrolü
            if not request.user.is_authenticated:
                return JsonResponse({'error': 'Giriş yapmanız gerekiyor'}, status=401)
            
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
                'location_name': location.name,
                'record_id': record.id
            })
            
        except Location.DoesNotExist:
            return JsonResponse({'error': 'Geçersiz lokasyon'}, status=404)
        except Employee.DoesNotExist:
            return JsonResponse({'error': 'Çalışan bulunamadı'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Geçersiz istek metodu'}, status=405)

@login_required
def get_employee_status(request):
    try:
        # Company kontrolü
        try:
            company = request.user.company
        except AttributeError:
            # Eğer user'ın company'si yoksa, employee olarak kontrol et
            try:
                employee = Employee.objects.get(user=request.user)
                company = employee.company
            except Employee.DoesNotExist:
                return JsonResponse({'error': 'Şirket bilgisi bulunamadı'}, status=400)
        
        employees = Employee.objects.filter(company=company, is_active=True)
        
        employee_statuses = []
        for employee in employees:
            last_record = AttendanceRecord.objects.filter(
                employee=employee
            ).order_by('-timestamp').first()
            
            status = {
                'employee_id': employee.id,
                'name': f"{employee.user.first_name} {employee.user.last_name}",
                'employee_code': employee.employee_id,
                'is_at_work': last_record.entry_type == 'IN' if last_record else False,
                'last_action': last_record.timestamp.isoformat() if last_record else None,
                'location': last_record.location.name if last_record else None,
                'entry_type': last_record.entry_type if last_record else None
            }
            employee_statuses.append(status)
            
        return JsonResponse({
            'employees': employee_statuses,
            'company_name': company.name
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_attendance_history(request):
    try:
        # Query parametrelerini al
        employee_id = request.GET.get('employee_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        limit = int(request.GET.get('limit', 50))
        
        # Employee belirleme
        if employee_id:
            try:
                employee = Employee.objects.get(id=employee_id)
                # Yetki kontrolü - sadece aynı şirketten çalışanları görebilir
                user_company = None
                try:
                    user_company = request.user.company
                except AttributeError:
                    try:
                        user_employee = Employee.objects.get(user=request.user)
                        user_company = user_employee.company
                    except Employee.DoesNotExist:
                        return JsonResponse({'error': 'Yetki hatası'}, status=403)
                
                if employee.company != user_company:
                    return JsonResponse({'error': 'Bu çalışanın kayıtlarını görme yetkiniz yok'}, status=403)
                    
            except Employee.DoesNotExist:
                return JsonResponse({'error': 'Çalışan bulunamadı'}, status=404)
        else:
            # Kendi kayıtlarını göster
            try:
                employee = Employee.objects.get(user=request.user)
            except Employee.DoesNotExist:
                return JsonResponse({'error': 'Çalışan profili bulunamadı'}, status=404)
        
        # Sorgu oluştur
        records_query = AttendanceRecord.objects.filter(employee=employee)
        
        # Tarih filtreleri
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                records_query = records_query.filter(timestamp__gte=start_datetime)
            except ValueError:
                return JsonResponse({'error': 'Geçersiz başlangıç tarihi formatı (YYYY-MM-DD)'}, status=400)
        
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                records_query = records_query.filter(timestamp__lt=end_datetime)
            except ValueError:
                return JsonResponse({'error': 'Geçersiz bitiş tarihi formatı (YYYY-MM-DD)'}, status=400)
        
        # Kayıtları al
        records = records_query.order_by('-timestamp')[:limit]
        
        # Response hazırla
        attendance_history = []
        for record in records:
            attendance_history.append({
                'id': record.id,
                'employee_name': f"{record.employee.user.first_name} {record.employee.user.last_name}",
                'employee_id': record.employee.id,
                'location_name': record.location.name,
                'entry_type': record.entry_type,
                'timestamp': record.timestamp.isoformat(),
                'gps_latitude': float(record.gps_latitude),
                'gps_longitude': float(record.gps_longitude),
                'is_valid_location': record.is_valid_location,
                'notes': record.notes
            })
        
        return JsonResponse({
            'attendance_history': attendance_history,
            'employee_name': f"{employee.user.first_name} {employee.user.last_name}",
            'total_records': len(attendance_history)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)