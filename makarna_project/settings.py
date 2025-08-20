import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv
import json

# --- TEMEL AYARLARI ---
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-yerel-icin-guvensiz-bir-anahtar')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# --- HOST AYARLARI (RENDER İÇİN GÜNCELLENDİ) ---
ALLOWED_HOSTS = []

# Render.com, deploy edilen servisin URL'sini bu ortam değişkeni ile sağlar.
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Kendi özel alan adınızı (custom domain) da bir ortam değişkeninden ekleyebilirsiniz.
allowed_hosts_env = os.environ.get('DJANGO_ALLOWED_HOSTS')
if allowed_hosts_env:
    ALLOWED_HOSTS.extend([host.strip() for host in allowed_hosts_env.split(',') if host.strip()])

# Geliştirme ortamı (DEBUG=True) için localhost ekler.
if DEBUG:
    ALLOWED_HOSTS.extend(['localhost', '127.0.0.1'])

AUTH_USER_MODEL = 'core.CustomUser'

# --- UYGULAMA TANIMLARI (CACHE EKLENDI) ---
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
    'django_redis',  # Redis cache için eklendi
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

# === REDIS CONFIGURATION (PERFORMANCE İÇİN ÖN TANIMLI) ===
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Upstash TLS/SSL bağlantıları için
if REDIS_URL.startswith('rediss://'):
    REDIS_URL += '?ssl_cert_reqs=none'

# --- VERİTABANI AYARLARI (RENDER PRODUCTION İÇİN OVERRIDE) ---
DATABASES = {
    'default': {}
}

# === RENDER İÇİN ZORLA IPv4 DATABASE URL ===
if not DEBUG:  # Production ortamında
    # Render için IPv4 Transaction Pooler kullan
    DATABASE_URL_OVERRIDE = "postgresql://postgres.sovfgoqxqggtizuaqqzi:0952koray1985Ka@aws-1-eu-central-1.pooler.supabase.com:6543/postgres"
    print(f"🔄 RENDER PRODUCTION: IPv4 Database URL kullanılıyor: {DATABASE_URL_OVERRIDE[:50]}...")
    
    DATABASES['default'] = dj_database_url.config(
        default=DATABASE_URL_OVERRIDE,
        conn_max_age=300,
        ssl_require=True,
        conn_health_checks=True,
    )
    
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'require',
        'connect_timeout': 5,
        'application_name': 'orderai_render',
    }
    
else:
    # Development için normal flow
    DATABASE_URL_ENV = os.environ.get('DATABASE_URL')
    
    if DATABASE_URL_ENV:
        DATABASES['default'] = dj_database_url.config(
            default=DATABASE_URL_ENV,
            conn_max_age=300,
            ssl_require=True,
            conn_health_checks=True,
        )
        
        DATABASES['default']['OPTIONS'] = {
            'sslmode': 'require',
            'connect_timeout': 5,
            'application_name': 'orderai_render',
        }
    else:
        print("--- LOKAL GELİŞTİRME: SQLite KULLANILIYOR ---")
        DATABASES['default'] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }

# === PERFORMANCE OPTİMİZASYONLARI ===
# Database connection pooling
DATABASES['default']['CONN_MAX_AGE'] = 300
DATABASES['default']['CONN_HEALTH_CHECKS'] = True

# === REDIS CACHE SİSTEMİ (HIZ İÇİN) ===
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 30,
                'retry_on_timeout': True,
                'socket_connect_timeout': 5,
                'socket_timeout': 5,
            },
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'PICKLER': 'pickle.dumps',
            'UNPICKLER': 'pickle.loads',
        },
        'KEY_PREFIX': 'orderai',
        'TIMEOUT': 300,  # 5 dakika default cache
        'VERSION': 1,
    }
}

# Session'ları Redis'te sakla (hızlandırma)
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 saat
SESSION_SAVE_EVERY_REQUEST = False  # Her request'te kaydetme

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

# --- STATİK VE MEDYA DOSYALARI (OPTİMİZE EDİLDİ) ---
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise optimizasyonları
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
WHITENOISE_MAX_AGE = 31536000  # 1 yıl cache
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'zip', 'gz', 'tgz', 'bz2', 'tbz', 'xz', 'br']

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'mediafiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- REST FRAMEWORK AYARLARI (CACHE İLE OPTİMİZE) ---
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'core.renderers.Utf8JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 20
}

# --- CORS AYARLARI ---
CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = [
    "https://order-ai-aaa115c18ca5.herokuapp.com",
    "http://127.0.0.1:60387",
    "http://localhost:60387",
]

# Render URL'sini de CORS'a eklemek için ortam değişkeni kullanıyoruz.
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')
if RENDER_EXTERNAL_URL:
    CORS_ALLOWED_ORIGINS.append(RENDER_EXTERNAL_URL)

# === CHANNELS CONFIGURATION ===
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [REDIS_URL],
            "capacity": 1500,
            "expiry": 60,
        },
    },
}

# === CELERY CONFIGURATION (OPTİMİZE EDİLDİ) ===
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Celery 6.0 hazırlığı için
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# === RENDER İÇİN MEMORY VE PERFORMANCE OPTİMİZE EDİLMİŞ CELERY AYARLARI ===
CELERY_WORKER_CONCURRENCY = 2  # Memory için düşük
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100
CELERY_WORKER_DISABLE_RATE_LIMITS = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Memory optimization
CELERY_WORKER_POOL_RESTARTS = True
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 200000  # 200MB limit per worker

# Performance optimization
CELERY_TASK_COMPRESSION = 'gzip'
CELERY_RESULT_COMPRESSION = 'gzip'
CELERY_TASK_ROUTES = {
    'send_bulk_order_notifications': {'queue': 'high_priority'},
    'send_order_update_notification': {'queue': 'high_priority'},
    'cleanup_old_notifications': {'queue': 'low_priority'},
}

# --- SIMPLE JWT AYARLARI (OPTİMİZE EDİLDİ) ---
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

# === GOOGLE & SUBSCRIPTION AYARLARI ===
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_PATH')

if not GOOGLE_APPLICATION_CREDENTIALS:
    local_credentials_path = os.path.join(BASE_DIR, 'google-credentials.json')
    if os.path.exists(local_credentials_path):
        GOOGLE_APPLICATION_CREDENTIALS = local_credentials_path
    else:
        print("UYARI: GOOGLE_APPLICATION_CREDENTIALS_PATH ayarlanmamış ve lokalde google-credentials.json bulunamadı. Abonelik doğrulama çalışmayabilir.")

ANDROID_PACKAGE_NAME = os.environ.get('ANDROID_PACKAGE_NAME', 'com.orderai.app')

# === SOCKET.IO AYARLARI (OPTİMİZE EDİLDİ) ===
SOCKETIO_SETTINGS = {
    'ping_timeout': 30000,  # 60000'den 30000'e düşürüldü
    'ping_interval': 15000,  # 25000'den 15000'e düşürüldü
    'max_http_buffer_size': 500000,  # 1MB'dan 500KB'a düşürüldü
    'allow_upgrades': True,
    'compression': True,
    'cookie': False,
    'cors_credentials': True,
}

SOCKETIO_SETTINGS['cors_allowed_origins'] = CORS_ALLOWED_ORIGINS

print("🚀 Production ortam - High Performance Socket.IO ayarları kullanılıyor")

SOCKETIO_ASYNC_MODE = 'threading'

# === LOGGING CONFIGURATION (PERFORMANCE İÇİN OPTİMİZE) ===
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.db.backends': {
            'level': 'WARNING',  # SQL query log'larını azalt
            'handlers': ['console'],
            'propagate': False,
        },
    },
}

# === DEBUG LOG AYARLARI ===
print(f"🔧 Socket.IO Ayarları (Optimized):")
print(f"   - Ping Timeout: {SOCKETIO_SETTINGS['ping_timeout']}ms")
print(f"   - Ping Interval: {SOCKETIO_SETTINGS['ping_interval']}ms")
print(f"   - Max HTTP Buffer: {SOCKETIO_SETTINGS['max_http_buffer_size']} bytes")
print(f"🔧 Celery Memory Optimization:")
print(f"   - Worker Concurrency: {CELERY_WORKER_CONCURRENCY}")
print(f"   - Max Tasks Per Child: {CELERY_WORKER_MAX_TASKS_PER_CHILD}")
print(f"   - Max Memory Per Child: {CELERY_WORKER_MAX_MEMORY_PER_CHILD}KB")
print(f"🔧 Database Optimization:")
print(f"   - Connection Max Age: {DATABASES['default']['CONN_MAX_AGE']}s")
print(f"   - Health Checks: {DATABASES['default']['CONN_HEALTH_CHECKS']}")
print(f"🔧 Cache System:")
print(f"   - Backend: Redis")
print(f"   - Default Timeout: {CACHES['default']['TIMEOUT']}s")