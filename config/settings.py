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
    "apps.billing.apps.BillingConfig", "apps.notifications.apps.NotificationsConfig", "apps.dashboard.apps.DashboardConfig", "apps.api.apps.ApiConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"], "libraries": {"notification_tags": "apps.notifications.templatetags.notification_tags", "theme_preview_media": "apps.photographers.templatetags.theme_preview_media"}}}]
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
STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

USE_SPACES = env_bool("USE_SPACES", False)
SPACES_ACCESS_KEY = os.getenv("SPACES_ACCESS_KEY", "")
SPACES_SECRET_KEY = os.getenv("SPACES_SECRET_KEY", "")
SPACES_BUCKET_NAME = os.getenv("SPACES_BUCKET_NAME", "")
SPACES_REGION = os.getenv("SPACES_REGION", "nyc3")
SPACES_ENDPOINT_URL = os.getenv("SPACES_ENDPOINT_URL", f"https://{SPACES_REGION}.digitaloceanspaces.com")
SPACES_SIGNED_URL_TTL = int(os.getenv("SPACES_SIGNED_URL_TTL", "900"))
if USE_SPACES and not all([SPACES_ACCESS_KEY, SPACES_SECRET_KEY, SPACES_BUCKET_NAME]):
    raise RuntimeError("Spaces credentials and bucket are required when USE_SPACES=1.")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:post-login-redirect"
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

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "1800"))
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
FREE_STORAGE_LIMIT_BYTES = int(os.getenv("FREE_STORAGE_LIMIT_BYTES", str(50 * 1024**3)))
MAX_GALLERY_UPLOAD_BYTES = int(os.getenv("MAX_GALLERY_UPLOAD_BYTES", str(100 * 1024**2)))

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
