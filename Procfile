web: gunicorn config.wsgi:application --config gunicorn.conf.py
worker: celery -A config worker --loglevel=INFO --concurrency=${CELERY_WORKER_CONCURRENCY:-2} --max-tasks-per-child=${CELERY_WORKER_MAX_TASKS_PER_CHILD:-500}
beat: celery -A config beat --loglevel=INFO --pidfile=
