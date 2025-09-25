# makarna_project/makarna_project/asgi.py


import os
import django
import socketio 
from django.core.asgi import get_asgi_application
from django.conf import settings # Ayarları import ediyoruz
import logging

# Django ayarlarını yükle
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'makarna_project.settings')
django.setup() 

# Celery worker gibi diğer süreçlerden gelen mesajları dinlemek için bir Redis yöneticisi oluştur.
redis_manager = socketio.AsyncRedisManager(settings.REDIS_URL)

# Socket.IO sunucu instance'ı
sio = socketio.AsyncServer(
    async_mode='asgi',
    client_manager=redis_manager, # Sunucuyu Redis yöneticisi ile başlat
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True
)

# Socket.IO event handler'larını import et ve kaydet
from core import socketio_handlers 
socketio_handlers.register_events(sio) 

# Django'nun ASGI uygulaması
django_app = get_asgi_application()

# Django ve Socket.IO'yu birleştir
application = socketio.ASGIApp(
    sio,              
    django_app,       
    socketio_path='/socket.io/' 
)
