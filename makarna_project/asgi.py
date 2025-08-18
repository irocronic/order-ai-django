# makarna_project/asgi.py
import os
import django
import socketio 
from django.core.asgi import get_asgi_application
import logging # logging için

# Django ayarlarını yükle
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'makarna_project.settings')
django.setup() 

# Socket.IO sunucu instance'ı
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*', # Üretim için '*' yerine belirli domainleri kullanın
    logger=True, # Socket.IO sunucu loglarını etkinleştir
    engineio_logger=True # Engine.IO loglarını etkinleştir (daha detaylı)
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