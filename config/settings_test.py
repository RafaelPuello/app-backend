"""
Test settings for app/backend.

Uses SQLite in-memory database and dummy secret key so tests run without
requiring environment variables or a real database connection.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "test-secret-key-not-for-production"

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "corsheaders",
    "ninja_extra",
    "domain",
    "nfctags",
    "botany",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

SITE_ID = 1

# Cache — use in-memory cache for tests (same backend as production; isolated per process)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "digidex-app-cache-test",
    }
}

# JWT settings — load the ID service public key for test token validation.
# The key pair lives in id/backend/config/keys/ (repo root is 4 levels above this file:
# config/settings_test.py → config/ → backend/ → app/ → repo root).
_ID_KEYS_DIR = BASE_DIR.parent.parent / "id" / "backend" / "config" / "keys"
_jwt_public_key_path = _ID_KEYS_DIR / "jwt_public_key.pem"

JWT_PUBLIC_KEY: str | None
try:
    JWT_PUBLIC_KEY = _jwt_public_key_path.read_text().strip()
except FileNotFoundError:
    # CI / environments without the ID service repo; tests will be skipped by
    # create_test_jwt_token when the private key is also missing.
    JWT_PUBLIC_KEY = None

JWT_ALGORITHM = "RS256"
JWT_ISSUER: str | None = None
JWT_AUDIENCE: str | None = None

# CORS
CORS_ALLOWED_ORIGINS: list[str] = []
CORS_ALLOW_CREDENTIALS = False
CSRF_TRUSTED_ORIGINS: list[str] = []

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Use PlantLabel as the concrete NFC tag model for MVP
NFC_TAG_MODEL = "domain.PlantLabel"

AUTHENTICATION_BACKENDS = [
    "config.auth.JWTAuthenticationBackend",
    "django.contrib.auth.backends.ModelBackend",
]
