# makarna_backend/core/apps.py

from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Bu satır, core/signals/__init__.py dosyasını çalıştırır
        # ve o dosyanın içindeki tüm sinyallerin kaydedilmesini sağlar.
        import core.signals