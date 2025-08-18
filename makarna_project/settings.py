# makarna_project/settings.py

import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv

# --- TEMEL AYARLAR ---
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-yerel-icin-guvensiz-bir-anahtar')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# --- HOST AYARLARI ---
HEROKU_APP_NAME = "makarna-project-2025-b5ed84d445c5.herokuapp.com"

allowed_hosts_env = os.environ.get('DJANGO_ALLOWED_HOSTS')
if allowed_hosts_env:
    ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(',') if host.strip()]
else:
    ALLOWED_HOSTS = []
    if DEBUG:
        ALLOWED_HOSTS.extend([
            'localhost',
            '127.0.0.1',
            '172.20.10.7',
            '192.168.1.249',
            '192.168.1.106',
            HEROKU_APP_NAME,
        ])
    else:
        if HEROKU_APP_NAME:
            ALLOWED_HOSTS.append(HEROKU_APP_NAME)
        pass

if not DEBUG and not ALLOWED_HOSTS:
    raise ValueError("Production'da ALLOWED_HOSTS boş olamaz. Lütfen DJANGO_ALLOWED_HOSTS ortam değişkenini ayarlayın.")

AUTH_USER_MODEL = 'core.CustomUser'

# --- UYGULAMA TANIMLARI ---
INSTALLED_APPS = [
    'whitenoise.runserver_nostatic',
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'channels',
    'subscriptions',
    'core.apps.CoreConfig',
]

# --- ARA YAZILIMLAR ---
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'makarna_project.urls'

# --- ŞABLON AYARLARI ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# --- UYGULAMA SUNUCULARI ---
WSGI_APPLICATION = 'makarna_project.wsgi.application'
ASGI_APPLICATION = 'makarna_project.asgi.application'

# --- VERİTABANI AYARLARI ---
DATABASES = {
    'default': {}
}

DATABASE_URL_ENV = os.environ.get('DATABASE_URL')

if DATABASE_URL_ENV:
    DATABASES['default'] = dj_database_url.config(
        default=DATABASE_URL_ENV,
        conn_max_age=0,
        ssl_require=os.environ.get('DATABASE_SSL_REQUIRE', 'True') == 'True'
    )
elif DEBUG:
    print("--- LOKAL GELİŞTİRME: SQLite KULLANILIYOR ---")
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
else:
    raise Exception("DATABASE_URL ortam değişkeni ayarlanmamış ve DEBUG=False. Production için veritabanı yapılandırılmalı.")

# --- ŞİFRE DOĞRULAMA ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# --- DİL VE ZAMAN AYARLARI ---
LANGUAGE_CODE = 'tr-tr'
TIME_ZONE = 'Europe/Istanbul'
USE_I18N = True
USE_TZ = True

# --- STATİK VE MEDYA DOSYALARI ---
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'mediafiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- REST FRAMEWORK AYARLARI ---
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'core.renderers.Utf8JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRerenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
}

# --- CORS AYARLARI ---
CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = [
    "https://order-ai-aaa115c18ca5.herokuapp.com",
    "http://127.0.0.1:60387",
    "http://localhost:60387",
]

# === DEĞİŞİKLİK BAŞLANGICI: Channels ve Celery için Redis Yapılandırması ===

# Heroku'da Redis eklentisi REDIS_URL ortam değişkenini otomatik sağlar.
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# =========================================================================================
# === SSL DÜZELTMESİ: Loglardaki hatayı çözmek için bu blok eklendi ===
# Celery'nin Heroku'daki güvenli Redis bağlantısı (rediss://) ile çalışabilmesi için
# SSL sertifika doğrulamasını atlaması gerektiğini belirtiyoruz.
if REDIS_URL.startswith('rediss://'):
    REDIS_URL += '?ssl_cert_reqs=CERT_NONE'
# =========================================================================================

# --- CHANNELS AYARLARI (REDIS KULLANACAK ŞEKİLDE GÜNCELLENDİ) ---
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [REDIS_URL],
        },
    },
}

# --- CELERY AYARLARI (YENİ EKLENDİ) ---
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# === DEĞİŞİKLİK SONU ===


# --- SIMPLE JWT AYARLARI ---
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.environ.get('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', '60'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.environ.get('JWT_REFRESH_TOKEN_LIFETIME_DAYS', '7'))),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    'JTI_CLAIM': 'jti',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# --- GÜVENLİK AYARLARI ---
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.environ.get('DJANGO_SECURE_SSL_REDIRECT', 'False') == 'True'
SESSION_COOKIE_SECURE = os.environ.get('DJANGO_SESSION_COOKIE_SECURE', 'False') == 'True'
CSRF_COOKIE_SECURE = os.environ.get('DJANGO_CSRF_COOKIE_SECURE', 'False') == 'True'

# --- E-POSTA AYARLARI ---
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.environ.get('DJANGO_EMAIL_HOST_USER', 'akma.koray@gmail.com')
    EMAIL_HOST_PASSWORD = os.environ.get('DJANGO_EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        print("*********************************************************************************")
        print("UYARI: Geliştirme ortamında (DEBUG=True) gerçek e-posta göndermek için")
        print(".env dosyanızda DJANGO_EMAIL_HOST_USER ve DJANGO_EMAIL_HOST_PASSWORD ")
        print("değişkenlerinin ayarlı olması gerekmektedir. Mevcut ayarlar eksik olduğundan")
        print("e-postalar konsola yazdırılacak (EMAIL_BACKEND console olarak ayarlanıyor).")
        print("*********************************************************************************")
        EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
        if not EMAIL_HOST_USER: EMAIL_HOST_USER = 'debug@example.com'
        if not DEFAULT_FROM_EMAIL: DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
    
    EMAIL_HOST_USER = os.environ.get('DJANGO_EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.environ.get('DJANGO_EMAIL_HOST_PASSWORD')
    
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        raise ValueError("Üretim ortamı için DJANGO_EMAIL_HOST_USER ve DJANGO_EMAIL_HOST_PASSWORD ortam değişkenleri ayarlanmalıdır.")

# --- YÖNETİCİ BİLDİRİM AYARLARI ---
ADMIN_EMAIL_RECIPIENTS_STR = os.environ.get('DJANGO_ADMIN_EMAIL_RECIPIENTS', 'akma.koray@gmail.com')
ADMIN_EMAIL_RECIPIENTS = [email.strip() for email in ADMIN_EMAIL_RECIPIENTS_STR.split(',') if email.strip()]

if not DEBUG and not ADMIN_EMAIL_RECIPIENTS:
    print("UYARI: Üretim ortamında yeni üyelik bildirimleri için DJANGO_ADMIN_EMAIL_RECIPIENTS ayarlanmamış.")
elif DEBUG and not ADMIN_EMAIL_RECIPIENTS:
    print("UYARI: Geliştirme ortamında yeni üyelik bildirimleri için DJANGO_ADMIN_EMAIL_RECIPIENTS ayarlanmamış. Bildirim gönderilmeyecek.")


# === GOOGLE & SUBSCRIPTION SETTINGS ===
SERVICE_ACCOUNT_FILE_NAME = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

if SERVICE_ACCOUNT_FILE_NAME:
    GOOGLE_APPLICATION_CREDENTIALS = os.path.join(BASE_DIR, SERVICE_ACCOUNT_FILE_NAME)
    
    if not os.path.exists(GOOGLE_APPLICATION_CREDENTIALS):
        print("*********************************************************************************")
        print(f"UYARI: Google servis anahtar dosyası bulunamadı!")
        print(f"Beklenen yol: {GOOGLE_APPLICATION_CREDENTIALS}")
        print("Lütfen .env dosyasındaki GOOGLE_APPLICATION_CREDENTIALS değişkeninin doğru olduğundan")
        print("ve dosyanın projenin ana dizininde bulunduğundan emin olun.")
        print("*********************************************************************************")
        GOOGLE_APPLICATION_CREDENTIALS = None
else:
    GOOGLE_APPLICATION_CREDENTIALS = None
    print("UYARI: .env dosyasında GOOGLE_APPLICATION_CREDENTIALS değişkeni ayarlanmamış. Abonelik doğrulama çalışmayacak.")

ANDROID_PACKAGE_NAME = os.environ.get('ANDROID_PACKAGE_NAME', 'com.orderai.app')
# === /GOOGLE & SUBSCRIPTION SETTINGS ===


# === GOOGLE SERVICE ACCOUNT DOSYASINI ENV'DEN YAZ ===
import json

service_json_str = os.environ.get("GOOGLE_SERVICE_JSON")

if service_json_str:
    credentials_path = os.path.join(BASE_DIR, 'google-credentials.json')
    
    try:
        # JSON'ı doğrula ve yaz
        service_json_data = json.loads(service_json_str)
        with open(credentials_path, 'w') as f:
            json.dump(service_json_data, f)

        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        GOOGLE_APPLICATION_CREDENTIALS = credentials_path
    except Exception as e:
        print("Google servis JSON dosyası yazılamadı:", e)
        GOOGLE_APPLICATION_CREDENTIALS = None
else:
    print("UYARI: GOOGLE_SERVICE_JSON Heroku ortam değişkeni olarak ayarlanmadı.")
    GOOGLE_APPLICATION_CREDENTIALS = None


# === SOCKET.IO AYARLARI - HEROKU OPTİMİZASYONU ===
# Socket.IO için özel ayarlar
SOCKETIO_SETTINGS = {
    'ping_timeout': 60000,          # 60 saniye - client'ın ping'e cevap vermesi için
    'ping_interval': 25000,         # 25 saniye - server'ın ping gönderme aralığı
    'max_http_buffer_size': 1000000, # 1MB - HTTP buffer size
    'allow_upgrades': True,         # WebSocket upgrade'e izin ver
    'compression': True,            # Veri sıkıştırma
    'cookie': False,               # Session cookie kullanma
    'cors_allowed_origins': CORS_ALLOWED_ORIGINS,  # CORS ayarlarını kullan
    'cors_credentials': True,       # Credentials ile CORS
}

# Heroku için özel ayarlar (Heroku detection)
if 'DYNO' in os.environ or 'herokuapp.com' in os.environ.get('HEROKU_APP_NAME', ''):
    print("🔧 Heroku ortamı tespit edildi - Socket.IO ayarları optimize ediliyor...")
    
    SOCKETIO_SETTINGS.update({
        'ping_timeout': 30000,      # Heroku için daha kısa timeout
        'ping_interval': 10000,     # Heroku için daha sık ping  
        'engineio_logger': True,    # Heroku'da debug için log
        'socketio_logger': True,    # Heroku'da debug için log
    })
    
    # Heroku için ek ayarlar
    HEROKU_SOCKETIO_CONFIG = {
        'transports': ['websocket', 'polling'],
        'upgrade_timeout': 10000,   # Upgrade için daha kısa süre
        'close_timeout': 10000,     # Connection kapanma timeout
    }
    
    SOCKETIO_SETTINGS.update(HEROKU_SOCKETIO_CONFIG)
else:
    print("🏠 Local/Production ortam - Normal Socket.IO ayarları kullanılıyor")

# Socket.IO server için async mode
SOCKETIO_ASYNC_MODE = 'threading'

# Request timeout ayarları
if 'DYNO' in os.environ:
    # Heroku için özel request timeout'ları
    DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
    FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
    
    # HTTP Keep-Alive ayarları Heroku için
    CONN_MAX_AGE = 0  # Heroku'da persistent connection problemi olabilir
else:
    # Normal ortam için
    CONN_MAX_AGE = 60

# === DYNO KEEP-ALIVE SİSTEMİ (OPSİYONEL) ===
# Heroku dyno'nun 30dk sonra sleep mode'a girmesini önlemek için

HEROKU_KEEP_ALIVE_ENABLED = os.environ.get('HEROKU_KEEP_ALIVE_ENABLED', 'True') == 'True'
HEROKU_KEEP_ALIVE_URL = os.environ.get('HEROKU_KEEP_ALIVE_URL', f"https://{HEROKU_APP_NAME}/api/health/")

if 'DYNO' in os.environ and HEROKU_KEEP_ALIVE_ENABLED:
    print(f"🏃‍♂️ Heroku Keep-Alive sistemi aktif: {HEROKU_KEEP_ALIVE_URL}")
    
    # Celery varsa keep-alive task'i için ayarlar
    try:
        from celery.schedules import crontab
        
        # Her 25 dakikada bir ping at
        CELERYBEAT_SCHEDULE = getattr(globals(), 'CELERYBEAT_SCHEDULE', {})
        CELERYBEAT_SCHEDULE['heroku-keep-alive'] = {
            'task': 'core.tasks.keep_dyno_awake',
            'schedule': crontab(minute='*/25'),  # Her 25 dakika
            'kwargs': {'url': HEROKU_KEEP_ALIVE_URL}
        }
    except ImportError:
        print("⚠️ Celery bulunamadı - Keep-alive task schedule edilemedi")

# === DEBUG LOG AYARLARI ===
print(f"🔧 Socket.IO Ayarları:")
print(f"   - Ping Timeout: {SOCKETIO_SETTINGS['ping_timeout']}ms")
print(f"   - Ping Interval: {SOCKETIO_SETTINGS['ping_interval']}ms") 
print(f"   - Heroku Mode: {'DYNO' in os.environ}")
print(f"   - Keep-Alive: {HEROKU_KEEP_ALIVE_ENABLED}")