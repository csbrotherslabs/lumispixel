"""Django settings for the LumisPixel project."""
import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def env_bool(name, default=False):
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}

def env_list(name, default=None):
    value = os.getenv(name)
    return (default or []) if value is None else [item.strip() for item in value.split(",") if item.strip()]

DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-development-only-change-me")
if not DEBUG and SECRET_KEY == "django-insecure-development-only-change-me":
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production.")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"] if DEBUG else ["lumispixel.com", "www.lumispixel.com"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [] if DEBUG else ["https://lumispixel.com", "https://www.lumispixel.com"])
PUBLIC_BASE_URL = os.getenv("DJANGO_PUBLIC_BASE_URL", "" if DEBUG else "https://lumispixel.com").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "storages", "apps.core.apps.CoreConfig", "apps.accounts.apps.AccountsConfig", "apps.photographers.apps.PhotographersConfig", "apps.clients.apps.ClientsConfig",
    "apps.galleries.apps.GalleriesConfig", "apps.ai_engine.apps.AiEngineConfig", "apps.broker.apps.BrokerConfig", "apps.marketplace.apps.MarketplaceConfig",
    "apps.billing.apps.BillingConfig", "apps.notifications.apps.NotificationsConfig", "apps.dashboard.apps.DashboardConfig", "apps.internal_ops.apps.InternalOpsConfig",
    "apps.workflows.apps.WorkflowsConfig", "apps.api.apps.ApiConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "apps.core.context_processors.marketing_pricing", "apps.internal_ops.context_processors.internal_workspace"], "libraries": {"notification_tags": "apps.notifications.templatetags.notification_tags", "theme_preview_media": "apps.photographers.templatetags.theme_preview_media"}}}]
WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "60")), conn_health_checks=True, ssl_require=env_bool("DB_SSL_REQUIRE", not DEBUG))}
elif DEBUG:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    raise RuntimeError("DATABASE_URL must be set in production.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"}, {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE_BACKEND = os.getenv(
    "DJANGO_STATICFILES_STORAGE",
    "whitenoise.storage.CompressedManifestStaticFilesStorage",
)
PRODUCTION_STATICFILES_STORAGE_BACKEND = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)
if not DEBUG and STATICFILES_STORAGE_BACKEND != PRODUCTION_STATICFILES_STORAGE_BACKEND:
    raise RuntimeError(
        "Production requires WhiteNoise CompressedManifestStaticFilesStorage."
    )
STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": STATICFILES_STORAGE_BACKEND}}
# Hashed WhiteNoise assets are content-addressed and safe to cache indefinitely.
# Non-hashed URLs retain WhiteNoise's conservative default caching behavior.
WHITENOISE_MAX_AGE = int(os.getenv("WHITENOISE_MAX_AGE", "60"))
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

# Gallery originals use an explicit provider so the application is not coupled
# to a single object-storage vendor. Local storage remains the safe default for
# development and CI; production should set GALLERY_STORAGE_BACKEND=b2.
GALLERY_STORAGE_BACKEND = os.getenv("GALLERY_STORAGE_BACKEND", "local").strip().lower()
if GALLERY_STORAGE_BACKEND not in {"local", "b2"}:
    raise RuntimeError("GALLERY_STORAGE_BACKEND must be one of: local, b2.")

GALLERY_STORAGE_ENVIRONMENT = os.getenv(
    "GALLERY_STORAGE_ENVIRONMENT", "dev" if DEBUG else "prod"
).strip().lower()
if GALLERY_STORAGE_ENVIRONMENT not in {"dev", "prod"}:
    raise RuntimeError("GALLERY_STORAGE_ENVIRONMENT must be either 'dev' or 'prod'.")

B2_ACCESS_KEY_ID = os.getenv("B2_ACCESS_KEY_ID", "")
B2_SECRET_ACCESS_KEY = os.getenv("B2_SECRET_ACCESS_KEY", "")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME", "")
B2_REGION = os.getenv("B2_REGION", "")
B2_ENDPOINT_URL = os.getenv("B2_ENDPOINT_URL", "").rstrip("/")
B2_SIGNED_URL_TTL = int(os.getenv("B2_SIGNED_URL_TTL", "900"))
B2_CONNECT_TIMEOUT_SECONDS = int(os.getenv("B2_CONNECT_TIMEOUT_SECONDS", "5"))
B2_READ_TIMEOUT_SECONDS = int(os.getenv("B2_READ_TIMEOUT_SECONDS", "30"))
B2_MAX_ATTEMPTS = int(os.getenv("B2_MAX_ATTEMPTS", "4"))
if B2_CONNECT_TIMEOUT_SECONDS <= 0 or B2_READ_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("B2 network timeouts must be positive.")
if B2_MAX_ATTEMPTS < 1 or B2_MAX_ATTEMPTS > 10:
    raise RuntimeError("B2_MAX_ATTEMPTS must be between 1 and 10.")
B2_MULTIPART_SIGNED_URL_TTL = int(os.getenv("B2_MULTIPART_SIGNED_URL_TTL", "900"))
# Browser resume remains available for this window before abandoned B2 multipart
# uploads are aborted and their reserved photographer quota is released.
B2_MULTIPART_STALE_AFTER_SECONDS = int(os.getenv("B2_MULTIPART_STALE_AFTER_SECONDS", str(24 * 60 * 60)))
B2_MULTIPART_MIN_PART_BYTES = 5 * 1024**2
B2_MULTIPART_MAX_PARTS = 10000
GALLERY_STORAGE_DELETION_MAX_ATTEMPTS = int(os.getenv("GALLERY_STORAGE_DELETION_MAX_ATTEMPTS", "10"))
if GALLERY_STORAGE_DELETION_MAX_ATTEMPTS < 1:
    raise RuntimeError("GALLERY_STORAGE_DELETION_MAX_ATTEMPTS must be positive.")

MEDIA_DELIVERY_BASE_URL = os.getenv(
    "MEDIA_DELIVERY_BASE_URL",
    "https://media-dev.lumispixel.com" if GALLERY_STORAGE_ENVIRONMENT == "dev" else "https://media.lumispixel.com",
).rstrip("/")
MEDIA_SIGNING_SECRET = os.getenv("MEDIA_SIGNING_SECRET", "")
MEDIA_SIGNED_URL_TTL = int(os.getenv("MEDIA_SIGNED_URL_TTL", "900"))
if MEDIA_SIGNED_URL_TTL <= 0 or MEDIA_SIGNED_URL_TTL > 3600:
    raise RuntimeError("MEDIA_SIGNED_URL_TTL must be between 1 and 3600 seconds.")
if GALLERY_STORAGE_BACKEND == "b2" and not all(
    [B2_ACCESS_KEY_ID, B2_SECRET_ACCESS_KEY, B2_BUCKET_NAME, B2_REGION, B2_ENDPOINT_URL]
):
    raise RuntimeError(
        "B2_ACCESS_KEY_ID, B2_SECRET_ACCESS_KEY, B2_BUCKET_NAME, B2_REGION, "
        "and B2_ENDPOINT_URL are required when GALLERY_STORAGE_BACKEND=b2."
    )
if not DEBUG:
    if GALLERY_STORAGE_BACKEND != "b2":
        raise RuntimeError("Production requires GALLERY_STORAGE_BACKEND=b2.")
    if GALLERY_STORAGE_ENVIRONMENT != "prod":
        raise RuntimeError("Production requires GALLERY_STORAGE_ENVIRONMENT=prod.")
    if not MEDIA_DELIVERY_BASE_URL.startswith("https://"):
        raise RuntimeError("Production MEDIA_DELIVERY_BASE_URL must use HTTPS.")
    if not MEDIA_SIGNING_SECRET:
        raise RuntimeError("MEDIA_SIGNING_SECRET is required for production signed media delivery.")
    if len(MEDIA_SIGNING_SECRET) < 32:
        raise RuntimeError("MEDIA_SIGNING_SECRET must be at least 32 characters in production.")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:post-login-redirect"

# Explicit session/CSRF defaults. Production upgrades the transport flags below.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(os.getenv("DJANGO_SESSION_COOKIE_AGE", str(14 * 24 * 60 * 60)))
SESSION_SAVE_EVERY_REQUEST = False
LOGOUT_REDIRECT_URL = "core:index"

EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "email-smtp.us-east-1.amazonaws.com")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("DJANGO_EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "LumisPixel <noreply@lumispixel.com>")
SERVER_EMAIL = os.getenv("DJANGO_SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_VERIFICATION_TIMEOUT_SECONDS = int(os.getenv("EMAIL_VERIFICATION_TIMEOUT_SECONDS", str(24 * 60 * 60)))
if EMAIL_VERIFICATION_TIMEOUT_SECONDS <= 0 or EMAIL_VERIFICATION_TIMEOUT_SECONDS > 7 * 24 * 60 * 60:
    raise RuntimeError("EMAIL_VERIFICATION_TIMEOUT_SECONDS must be between 1 second and 7 days.")

if not DEBUG:
    if not ALLOWED_HOSTS:
        raise RuntimeError("DJANGO_ALLOWED_HOSTS must not be empty in production.")
    if not CSRF_TRUSTED_ORIGINS or any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
        raise RuntimeError("DJANGO_CSRF_TRUSTED_ORIGINS must contain HTTPS origins in production.")
    if not PUBLIC_BASE_URL.startswith("https://"):
        raise RuntimeError("DJANGO_PUBLIC_BASE_URL must use HTTPS in production.")
    if not DATABASE_URL or not DATABASE_URL.lower().startswith(("postgresql://", "postgres://")):
        raise RuntimeError("Production DATABASE_URL must use PostgreSQL.")
    if not B2_ENDPOINT_URL.startswith("https://"):
        raise RuntimeError("Production B2_ENDPOINT_URL must use HTTPS.")
    if not EMAIL_HOST or not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        raise RuntimeError("Production SMTP host and credentials are required.")
    if EMAIL_USE_TLS == EMAIL_USE_SSL:
        raise RuntimeError("Production email must enable exactly one of TLS or SSL.")

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
if not DEBUG:
    for setting_name, redis_url in {
        "CELERY_BROKER_URL": CELERY_BROKER_URL,
        "CELERY_RESULT_BACKEND": CELERY_RESULT_BACKEND,
    }.items():
        if not redis_url.startswith("rediss://"):
            raise RuntimeError(f"{setting_name} must use rediss:// in production.")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT = False
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "1500"))
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "1800"))
if CELERY_TASK_SOFT_TIME_LIMIT <= 0 or CELERY_TASK_TIME_LIMIT <= CELERY_TASK_SOFT_TIME_LIMIT:
    raise RuntimeError("CELERY_TASK_TIME_LIMIT must be greater than CELERY_TASK_SOFT_TIME_LIMIT.")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_RETRY = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = int(os.getenv("CELERY_BROKER_CONNECTION_MAX_RETRIES", "20"))
if CELERY_BROKER_CONNECTION_MAX_RETRIES < 0:
    raise RuntimeError("CELERY_BROKER_CONNECTION_MAX_RETRIES must be non-negative.")
CELERY_VISIBILITY_TIMEOUT = int(os.getenv("CELERY_VISIBILITY_TIMEOUT", "3600"))
if CELERY_VISIBILITY_TIMEOUT <= CELERY_TASK_TIME_LIMIT:
    raise RuntimeError(
        "CELERY_VISIBILITY_TIMEOUT must be greater than CELERY_TASK_TIME_LIMIT "
        "so Redis cannot redeliver a task while a worker may still be executing it."
    )
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": CELERY_VISIBILITY_TIMEOUT,
}
CELERY_RESULT_EXPIRES = int(os.getenv("CELERY_RESULT_EXPIRES", "86400"))
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_BEAT_SCHEDULE = {
    "scan-scheduled-workflow-automations": {
        "task": "apps.workflows.tasks.scan_scheduled_automations",
        "schedule": 3600.0,
    },
    "cleanup-stale-gallery-multipart-uploads": {
        "task": "apps.galleries.tasks.cleanup_stale_gallery_multipart_uploads",
        "schedule": 3600.0,
    },
    "cleanup-gallery-storage-objects": {
        "task": "apps.galleries.tasks.cleanup_gallery_storage_objects",
        "schedule": 3600.0,
    },
}
FREE_STORAGE_LIMIT_BYTES = int(os.getenv("FREE_STORAGE_LIMIT_BYTES", str(50 * 1024**3)))
MAX_GALLERY_UPLOAD_BYTES = int(os.getenv("MAX_GALLERY_UPLOAD_BYTES", str(100 * 1024**2)))
MAX_GALLERY_IMAGE_PIXELS = int(os.getenv("MAX_GALLERY_IMAGE_PIXELS", "100000000"))

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
