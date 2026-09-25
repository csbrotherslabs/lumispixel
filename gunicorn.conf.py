"""Gunicorn production configuration for LumisPixel.

Keep request execution bounded and recycle workers defensively. Browser uploads go
straight to B2, so Django workers should not need multi-minute request lifetimes.
"""

import multiprocessing
import os


bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", str(min((multiprocessing.cpu_count() * 2) + 1, 4))))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
threads = int(os.getenv("GUNICORN_THREADS", "2"))

timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

limit_request_line = int(os.getenv("GUNICORN_LIMIT_REQUEST_LINE", "4094"))
limit_request_fields = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELDS", "100"))
limit_request_field_size = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELD_SIZE", "8190"))

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
capture_output = True

# Cloudflare / the platform terminates TLS. Django separately trusts the
# X-Forwarded-Proto contract via SECURE_PROXY_SSL_HEADER.
forwarded_allow_ips = os.getenv("GUNICORN_FORWARDED_ALLOW_IPS", "127.0.0.1")

# Do not preload Django by default: each worker initializes its own DB/network
# state and a bad worker can be replaced without inheriting master-process state.
preload_app = False
