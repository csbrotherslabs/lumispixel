web: gunicorn config.wsgi:application --config gunicorn.conf.py
worker: celery -A config worker --loglevel=INFO --concurrency=2
beat: celery -A config beat --loglevel=INFO
