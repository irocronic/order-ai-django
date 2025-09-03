#!/usr/bin/env bash
# exit on error
set -o errexit

echo "🔧 Build process başlatılıyor..."

# Dependencies yükle
echo "📦 Dependencies yükleniyor..."
pip install --upgrade pip
pip install -r requirements.txt

# Static files collect et
echo "📁 Static files collect ediliyor..."
python manage.py collectstatic --noinput --verbosity=1

# Database bağlantısını test et ve migration'ları çalıştır
echo "🗄️ Database migration işlemi başlatılıyor..."
python -c "
import os
import sys
import time
import django
from django.conf import settings

# Django'yu başlat
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'makarna_project.settings')
django.setup()

from django.core.management import execute_from_command_line
from django.db import connection
from django.db.utils import OperationalError

def test_db_connection():
    \"\"\"Database bağlantısını test et\"\"\"
    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(f'🔄 DB bağlantı testi {attempt + 1}/{max_retries}')
            connection.ensure_connection()
            
            # Basit bir sorgu çalıştır
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                result = cursor.fetchone()
            
            print(f'✅ DB bağlantısı başarılı - Test sonucu: {result[0]}')
            return True
            
        except OperationalError as e:
            print(f'❌ Deneme {attempt + 1} başarısız: {str(e)[:80]}...')
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8, 16 saniye
                print(f'⏳ {wait_time} saniye bekleniyor...')
                time.sleep(wait_time)
            else:
                print('❌ Tüm bağlantı denemeleri başarısız!')
                return False
        except Exception as e:
            print(f'❌ Beklenmeyen hata: {type(e).__name__}: {e}')
            return False
    
    return False

def run_migrations():
    \"\"\"Migration'ları çalıştır\"\"\"
    try:
        print('🚀 Migration işlemi başlatılıyor...')
        
        # Migration durumunu kontrol et
        from django.db.migrations.executor import MigrationExecutor
        from django.db import DEFAULT_DB_ALIAS, connections
        
        connection = connections[DEFAULT_DB_ALIAS]
        executor = MigrationExecutor(connection)
        
        # Pending migration'ları kontrol et
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        
        if plan:
            print(f'📋 {len(plan)} adet migration uygulanacak')
            for migration, backwards in plan:
                direction = 'Geri' if backwards else 'İleri'
                print(f'   - {direction}: {migration.app_label}.{migration.name}')
        else:
            print('📋 Uygulanacak yeni migration yok')
        
        # Migration'ları çalıştır
        execute_from_command_line(['manage.py', 'migrate', '--verbosity=2'])
        print('✅ Migration işlemi tamamlandı')
        return True
        
    except Exception as e:
        print(f'❌ Migration hatası: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        return False

# Ana işlem
print('🔍 Database bağlantısı kontrol ediliyor...')
if test_db_connection():
    print('🔄 Migration işlemi başlatılıyor...')
    if run_migrations():
        print('✅ Tüm database işlemleri başarılı!')
        sys.exit(0)
    else:
        print('❌ Migration işlemi başarısız!')
        sys.exit(1)
else:
    print('❌ Database bağlantısı kurulamadı!')
    sys.exit(1)
"

echo "✅ Build process başarıyla tamamlandı!"