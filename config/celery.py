import os
from urllib.parse import parse_qs, urlparse

from celery import Celery


def _env_bool(name, default=False):
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def validate_production_redis_tls(redis_url, setting_name):
    """Fail closed when a production Celery Redis URL does not verify TLS."""
    parsed = urlparse(redis_url)
    query = parse_qs(parsed.query)

    if parsed.scheme != "rediss":
        raise RuntimeError(f"{setting_name} must use rediss:// in production.")
    if query.get("ssl_cert_reqs") != ["required"]:
        raise RuntimeError(
            f"{setting_name} must set ssl_cert_reqs=required in production."
        )
    ca_paths = query.get("ssl_ca_certs")
    if not ca_paths or not ca_paths[0]:
        raise RuntimeError(
            f"{setting_name} must set ssl_ca_certs to the trusted Redis CA in production."
        )


if not _env_bool("DJANGO_DEBUG", True):
    broker_url = os.getenv("CELERY_BROKER_URL", "")
    result_backend = os.getenv("CELERY_RESULT_BACKEND", broker_url)
    validate_production_redis_tls(broker_url, "CELERY_BROKER_URL")
    validate_production_redis_tls(result_backend, "CELERY_RESULT_BACKEND")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
app = Celery("lumispixel")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
