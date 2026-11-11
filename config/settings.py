"""Configuration Django de Kora. Tout ce qui varie passe par l'environnement."""
from pathlib import Path

import environ
from django.contrib.messages import constants as message_constants
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    SECURE_SSL_REDIRECT=(bool, False),
    UPLOAD_MAX_MB=(int, 5),
    PORTFOLIO_MAX_ITEMS=(int, 20),
)
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env("DJANGO_DEBUG")
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key" if DEBUG else None)
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")

# Prise en charge automatique de l'hôte Render (*.onrender.com)
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_EXTERNAL_HOSTNAME:
    if RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    render_origin = f"https://{RENDER_EXTERNAL_HOSTNAME}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)

# Prise en charge automatique des domaines Railway (*.up.railway.app et RAILWAY_PUBLIC_DOMAIN)
RAILWAY_PUBLIC_DOMAIN = env("RAILWAY_PUBLIC_DOMAIN", default="")
RAILWAY_STATIC_URL = env("RAILWAY_STATIC_URL", default="")
if RAILWAY_PUBLIC_DOMAIN or RAILWAY_STATIC_URL or env("RAILWAY_ENVIRONMENT", default=""):
    if ".up.railway.app" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(".up.railway.app")
    if "https://*.up.railway.app" not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append("https://*.up.railway.app")
    if RAILWAY_PUBLIC_DOMAIN and RAILWAY_PUBLIC_DOMAIN not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
        CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_PUBLIC_DOMAIN}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sitemaps",
    # Apps Kora
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.providers",
    "apps.requests_app",
    "apps.reviews",
    "apps.messaging",
    "apps.notifications",
    "apps.favorites",
    "apps.cms",
    "apps.dashboard_admin",
    "apps.dashboard_provider",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "apps.core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
if not DEBUG and DATABASES["default"].get("ENGINE") != "django.db.backends.sqlite3":
    DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=600)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Authentification -------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.EmailOrPhoneBackend"]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

# --- i18n -------------------------------------------------------------------
LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", _("Français")), ("en", _("English"))]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

# --- Fichiers statiques et médias ------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}
WHITENOISE_MANIFEST_STRICT = env.bool("WHITENOISE_MANIFEST_STRICT", default=False)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Documents sensibles (pièces d'identité) : dossier distinct, non exposé par le serveur web.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

UPLOAD_MAX_MB = env("UPLOAD_MAX_MB")
PORTFOLIO_MAX_ITEMS = env("PORTFOLIO_MAX_ITEMS")
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# --- E-mail, SMS ------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Kora <no-reply@kora.cm>")
SMS_BACKEND = env("SMS_BACKEND", default="console")
SUPPORT_WHATSAPP = env("SUPPORT_WHATSAPP", default="")
# Réseaux sociaux : un lien n'apparaît dans le pied de page que s'il est renseigné.
SOCIAL_LINKS = {
    name: env(f"SOCIAL_{name.upper()}", default="")
    for name in ("facebook", "instagram", "tiktok", "youtube")
}

# --- Messages (classes utilisées par les toasts Tailwind) -------------------
MESSAGE_TAGS = {
    message_constants.DEBUG: "info",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "error",
}

# --- Sécurité ---------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # deux semaines d'inactivité maximum
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
