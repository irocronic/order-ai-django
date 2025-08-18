# makarna_project/__init__.py

# Bu satır, Django başladığında paylaşılan görevlerimizin (shared_task)
# Celery uygulaması tarafından bulunmasını sağlar.
from .celery import app as celery_app

__all__ = ('celery_app',)