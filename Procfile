release: python manage.py migrate
web: gunicorn makarna_project.asgi:application -k uvicorn.workers.UvicornWorker --log-file -
worker: celery -A makarna_project worker -l info
