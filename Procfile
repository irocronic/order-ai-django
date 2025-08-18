release: python manage.py migrate
web: uvicorn makarna_project.asgi:application --host 0.0.0.0 --port $PORT --ws-ping-interval 20