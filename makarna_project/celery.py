# makarna_project/celery.py

import os
from celery import Celery

# Django'nun 'settings' modülünü Celery için varsayılan olarak ayarla.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'makarna_project.settings')

# Celery uygulamasını oluştur
app = Celery('makarna_project')

# Django ayarlarını kullanarak Celery'yi yapılandır.
# namespace='CELERY' demek, tüm Celery ayarlarının 'CELERY_' prefix'i ile başlaması gerektiği anlamına gelir.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django app'lerindeki tüm task modüllerini (tasks.py) otomatik olarak bul.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')