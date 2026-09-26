from pathlib import Path
import secrets
from django.core.exceptions import ImproperlyConfigured
from context_me.access import ROOT, is_hosted, setting
from .database import database_config

BASE_DIR = ROOT
HOSTED = is_hosted()
DATA_DIR = Path(setting("CONTEXT_ME_DATA_DIR", str(ROOT / "data"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
SECRET_KEY = setting("DJANGO_SECRET_KEY")
if HOSTED:
    if len(SECRET_KEY) < 50:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a random secret of at least 50 characters.")
    if len(setting("ADMIN_PASSWORD")) < 16:
        raise ImproperlyConfigured("Set ADMIN_PASSWORD to at least 16 characters.")
if not SECRET_KEY:
    secret_file = DATA_DIR / ".django-secret"
    try:
        with secret_file.open("x", encoding="utf-8") as handle:
            handle.write(secrets.token_urlsafe(64))
        secret_file.chmod(0o600)
    except FileExistsError:
        pass
    SECRET_KEY = secret_file.read_text(encoding="utf-8").strip()

DEBUG = not HOSTED and setting("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [s.strip() for s in setting("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",") if s.strip()]
if HOSTED and ("*" in ALLOWED_HOSTS or not setting("DJANGO_ALLOWED_HOSTS")):
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS to your exact host names, separated by commas.")
CSRF_TRUSTED_ORIGINS = [s.strip() for s in setting("DJANGO_CSRF_TRUSTED_ORIGINS").split(",") if s.strip()]
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
                  "django.contrib.messages", "django.contrib.staticfiles", "webapp"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware",
              "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
              "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
              "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
              "webapp.middleware.PrivateResponsesMiddleware"]
ROOT_URLCONF = "webapp.urls"
WSGI_APPLICATION = "webapp.wsgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"],
              "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request",
              "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
DATABASES = {"default": database_config(
    setting("DATABASE_URL").strip(), DATA_DIR, cloud_run=bool(setting("K_SERVICE")),
    allow_temporary=setting("ALLOW_TEMPORARY_DATABASE", "false").lower() == "true")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 16}}]
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/library/"
LOGOUT_REDIRECT_URL = "/"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 3600
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = HOSTED
CSRF_COOKIE_SECURE = HOSTED
CSRF_FAILURE_VIEW = "webapp.views.csrf_failure"
SECURE_SSL_REDIRECT = HOSTED
SECURE_HSTS_SECONDS = 31536000 if HOSTED else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = HOSTED
SECURE_HSTS_PRELOAD = HOSTED
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# Enable only behind a trusted HTTPS proxy (Cloud Run).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if HOSTED else None
STATIC_URL = "/static/"
STATIC_ROOT = DATA_DIR / "static"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}
DATA_UPLOAD_MAX_MEMORY_SIZE = 22 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 1
LANGUAGE_CODE = "en"
TIME_ZONE = "Europe/Helsinki"
USE_TZ = True
