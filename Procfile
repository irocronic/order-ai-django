release: python manage.py migrate
web: daphne -p $PORT -b 0.0.0.0 makarna_project.asgi:application
worker: celery -A makarna_project worker -l info