# makarna_project/settings.py

import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv
import json
import ssl  # SSL ayarları için gerekli

# --- TEMEL AYARLARI ---
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-yerel-icin-guvensiz-bir-anahtar')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# --- HOST AYARLARI ---
ALLOWED_HOSTS = []
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
allowed_hosts_env = os.environ.get('DJANGO_ALLOWED_HOSTS')
if allowed_hosts_env:
    ALLOWED_HOSTS.extend([host.strip() for host in allowed_hosts_env.split(',') if host.strip()])
if DEBUG:
    ALLOWED_HOSTS.extend(['localhost', '127.0.0.1'])

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
    'templates',
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

# --- VERİTABANI AYARLARI (NEON.TECH POOLED CONNECTION İÇİN FİX) ---
DATABASES = {
    'default': {}
}

DATABASE_URL_ENV = os.environ.get('DATABASE_URL')
if DATABASE_URL_ENV:
    if DATABASE_URL_ENV.strip() == '':
        raise Exception("DATABASE_URL environment variable is empty. Please set a valid PostgreSQL connection string from Neon.tech.")
    
    DATABASES['default'] = dj_database_url.config(
        default=DATABASE_URL_ENV,
        conn_max_age=600,
        ssl_require=True,
    )
    DATABASES['default']['OPTIONS'] = {
        'connect_timeout': 10,
        'sslmode': 'require',
        'application_name': 'orderai_django',
    }
    print(f"✅ Neon.tech PostgreSQL (Pooled) veritabanı yapılandırıldı")
    print(f"   - Host: {DATABASES['default'].get('HOST', 'N/A')}")
    print(f"   - Database: {DATABASES['default'].get('NAME', 'N/A')}")
    
elif DEBUG:
    print("--- LOKAL GELİŞTİRME: SQLite KULLANILIYOR ---")
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
else:
    raise Exception("DATABASE_URL ortam değişkeni ayarlanmamış ve DEBUG=False. Production için Neon.tech veritabanı yapılandırılmalı.")

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
        'rest_framework.renderers.BrowsableAPIRenderer',
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
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')
if RENDER_EXTERNAL_URL:
    CORS_ALLOWED_ORIGINS.append(RENDER_EXTERNAL_URL)

# === REDIS SSL BAĞLANTI YAPILANDIRMASI ===
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

def patch_redis_url(url, extra_params: dict):
    if url.startswith('rediss://'):
        from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode
        split = urlsplit(url)
        query = parse_qs(split.query)
        for k, v in extra_params.items():
            if k not in query:
                query[k] = [v]
        new_query = urlencode(query, doseq=True)
        return urlunsplit((split.scheme, split.netloc, split.path, new_query, split.fragment))
    return url

channel_redis_url = patch_redis_url(
    REDIS_URL,
    {
        "ssl_cert_reqs": "required",
        "ssl_ca_certs": os.path.join(BASE_DIR, "upstash.crt"),
    }
)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [channel_redis_url],
        },
    },
}

CELERY_BROKER_URL = patch_redis_url(
    REDIS_URL,
    {"ssl_cert_reqs": "CERT_REQUIRED"}
)
CELERY_RESULT_BACKEND = patch_redis_url(
    REDIS_URL,
    {"ssl_cert_reqs": "CERT_REQUIRED"}
)
if REDIS_URL.startswith('rediss://'):
    ssl_options = {
        'ssl_cert_reqs': ssl.CERT_REQUIRED,
        'ssl_ca_certs': os.path.join(BASE_DIR, "upstash.crt")
    }
    CELERY_BROKER_TRANSPORT_OPTIONS = ssl_options
    CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = ssl_options

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_WORKER_CONCURRENCY = 2
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100
CELERY_WORKER_DISABLE_RATE_LIMITS = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_POOL_RESTARTS = True
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 200000

# --- SIMPLE JWT AYARLARI ---
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.environ.get('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', '120'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.environ.get('JWT_REFRESH_TOKEN_LIFETIME_DAYS', '7'))),
    'ROTATE_REFRESH_TOKENS': True,
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

# --- GOOGLE & SUBSCRIPTION AYARLARI ---
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_PATH')
if not GOOGLE_APPLICATION_CREDENTIALS:
    local_credentials_path = os.path.join(BASE_DIR, 'google-credentials.json')
    if os.path.exists(local_credentials_path):
        GOOGLE_APPLICATION_CREDENTIALS = local_credentials_path
    else:
        print("UYARI: GOOGLE_APPLICATION_CREDENTIALS_PATH ayarlanmamış ve lokalde google-credentials.json bulunamadı. Abonelik doğrulama çalışmayabilir.")

ANDROID_PACKAGE_NAME = os.environ.get('ANDROID_PACKAGE_NAME', 'com.orderai.app')

# --- SOCKET.IO AYARLARI ---
SOCKETIO_SETTINGS = {
    'ping_timeout': 60000,
    'ping_interval': 25000,
    'max_http_buffer_size': 1000000,
    'allow_upgrades': True,
    'compression': True,
    'cookie': False,
    'cors_credentials': True,
}
SOCKETIO_SETTINGS['cors_allowed_origins'] = CORS_ALLOWED_ORIGINS
print("🏠 Production ortam - Memory Optimized Socket.IO ayarları kullanılıyor")
SOCKETIO_ASYNC_MODE = 'threading'

# --- DEBUG LOG AYARLARI ---
print(f"🔧 Socket.IO Ayarları:")
print(f"   - Ping Timeout: {SOCKETIO_SETTINGS['ping_timeout']}ms")
print(f"   - Ping Interval: {SOCKETIO_SETTINGS['ping_interval']}ms")
print(f"🔧 Celery Memory Optimization:")
print(f"   - Worker Concurrency: {CELERY_WORKER_CONCURRENCY}")
print(f"   - Max Tasks Per Child: {CELERY_WORKER_MAX_TASKS_PER_CHILD}")
print(f"   - Max Memory Per Child: {CELERY_WORKER_MAX_MEMORY_PER_CHILD}KB")

# --- ENCRYPTED MODEL FIELDS AYARI ---
FIELD_ENCRYPTION_KEY = os.environ.get(
    'DJANGO_FIELD_ENCRYPTION_KEY',
    'lCDG_OQWmZY4GGVtjACes8bZZZ4j73euPH0sjC5Omj0='
)
