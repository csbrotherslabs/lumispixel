web: gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120
worker: celery -A config worker --loglevel=INFO --concurrency=2
beat: celery -A config beat --loglevel=INFO
