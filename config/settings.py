"""
Django settings for the Dx Clinical Laboratory Information System.

Ported from the original Next.js/Drizzle implementation. Configuration is
driven by environment variables (see .env.example); a .env file in the project
root is loaded automatically in development.
"""
from pathlib import Path
import json
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ── Core ─────────────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Dx applications
    "apps.audit",
    "apps.accounts",
    "apps.patients",
    "apps.laboratory",
    "apps.clinical",
    "apps.quality",
    "apps.inventory",
    "apps.specialty",
    "apps.operations",
    "apps.billing",
    "apps.reporting",
    "apps.interop",
    "apps.compliance",
    "apps.rules",
    "apps.api",
    "apps.help",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Dx: binds the request (user, IP, agent, request id) to the audit context.
    # Must precede anything that writes data so events are attributable.
    "apps.audit.middleware.AuditContextMiddleware",
    # Dx: forces authentication on every view except an explicit allow-list.
    "apps.accounts.middleware.LoginRequiredMiddleware",
    # Dx: enforces password expiry, idle auto-logoff and account lockout.
    "apps.compliance.middleware.RegulatorySessionMiddleware",
    # Dx: refuses patient-facing screens to roles barred from them (installer).
    # Placed before the access log so a refused request is not recorded as a
    # PHI access that never happened.
    "apps.accounts.phi_barrier.PHIBarrierMiddleware",
    # Dx: records PHI access for HIPAA disclosure accounting.
    "apps.compliance.middleware.PHIAccessLogMiddleware",
    # Dx: refuses every write while the system is in read-only mode. Last, so
    # a refused write has already been authenticated and attributed — a
    # rejection during recovery is still something you want to be able to
    # trace.
    "apps.operations.readonly.ReadOnlyModeMiddleware",
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
                "apps.accounts.context_processors.navigation",
                "apps.operations.context_processors.active_alerts",
                "apps.compliance.context_processors.compliance_banner",
            ],
            "builtins": ["apps.common.templatetags.dx"],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ── Database ─────────────────────────────────────────────────────────────────

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "dx"),
        "USER": os.environ.get("POSTGRES_USER", "dx"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "dx"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── Authentication ───────────────────────────────────────────────────────────

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    # Verifies bcrypt hashes carried over from the Next.js implementation and
    # transparently upgrades any surviving cleartext passwords.
    "apps.accounts.backends.LegacyCompatibleBackend",
    "django.contrib.auth.backends.ModelBackend",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Two-factor authentication ────────────────────────────────────────────────
#
# TOTP (RFC 6238), implemented in apps/accounts/mfa.py. Required by default for
# the two roles that can change who else has access: somebody who can create an
# administrator account is a far more valuable target than somebody who can
# enter a potassium. Set MFA_REQUIRED_ROLES to widen or narrow it.
MFA_ENABLED = env_bool("MFA_ENABLED", True)
MFA_REQUIRED_ROLES = env_list("MFA_REQUIRED_ROLES", "installer,admin")


# ── Single sign-on (OpenID Connect) ──────────────────────────────────────────
#
# Off unless an issuer and client id are set. Authorization Code flow with
# PKCE; ID tokens verified against the issuer's JWKS. See apps/accounts/sso.py.
#
# The installer account is never authenticated through SSO — it is the
# break-glass account for the case where SSO itself is what has failed.
OIDC_ENABLED = env_bool("OIDC_ENABLED", False)
OIDC_PROVIDER_NAME = os.environ.get("OIDC_PROVIDER_NAME", "your organisation account")
OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "")
OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET", "")
OIDC_REDIRECT_URI = os.environ.get("OIDC_REDIRECT_URI", "")
OIDC_SCOPES = os.environ.get("OIDC_SCOPES", "openid profile email")
OIDC_USERNAME_CLAIM = os.environ.get("OIDC_USERNAME_CLAIM", "preferred_username")
OIDC_ROLE_CLAIM = os.environ.get("OIDC_ROLE_CLAIM", "groups")
# {"directory group": "dx role"}. Anything unmapped falls to OIDC_DEFAULT_ROLE,
# which is None — meaning refused rather than guessed at.
OIDC_ROLE_MAP = json.loads(os.environ.get("OIDC_ROLE_MAP", "{}"))
OIDC_DEFAULT_ROLE = os.environ.get("OIDC_DEFAULT_ROLE") or None
# Create a local account on first sign-in. Off by default: on a system holding
# patient records, somebody should decide that a person gets an account.
OIDC_PROVISION_USERS = env_bool("OIDC_PROVISION_USERS", False)


LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "operations:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# Matches the 24-hour session lifetime of the original implementation.
SESSION_COOKIE_AGE = 60 * 60 * 24
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

CSRF_COOKIE_HTTPONLY = False  # read by the HTMX request header hook
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)


# ── Internationalisation ─────────────────────────────────────────────────────

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


# ── Static & media ───────────────────────────────────────────────────────────

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Uploaded controlled documents (SOPs, policies) live under MEDIA_ROOT.
DOCUMENT_UPLOAD_SUBDIR = "documents"
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024


# ── Email (report distribution) ──────────────────────────────────────────────

EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "dx-lis@example.org")


# ── Dx domain settings ───────────────────────────────────────────────────────

# Shared secret the instrument middleware presents on POST /api/middleware/ingest/.
INSTRUMENT_INGEST_TOKEN = os.environ.get("INSTRUMENT_INGEST_TOKEN", "")

# Record locks expire after this many seconds of inactivity.
RECORD_LOCK_TTL_SECONDS = int(os.environ.get("RECORD_LOCK_TTL_SECONDS", "900"))

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"


# ── Cache ────────────────────────────────────────────────────────────────────
#
# The default is per-process local memory, which is fine for a single-process
# development server and **wrong for any multi-worker deployment**: anything
# counted in the cache is then counted once per worker. The API rate limiter is
# the case that matters — with four gunicorn workers and no shared cache, a
# client gets four times the limit it was given.
#
# Set DJANGO_CACHE_BACKEND and DJANGO_CACHE_LOCATION to something shared
# (Redis, Memcached, or the database cache table) before running more than one
# worker. `manage.py check` refuses to stay quiet about it.
CACHES = {
    "default": {
        "BACKEND": os.environ.get(
            "DJANGO_CACHE_BACKEND", "django.core.cache.backends.locmem.LocMemCache"
        ),
        "LOCATION": os.environ.get("DJANGO_CACHE_LOCATION", "dx-default"),
    }
}

TEST_RUNNER = "config.test_runner.DxTestRunner"


# ── Audit trail ──────────────────────────────────────────────────────────────

# Events that cannot reach the database are spooled here and replayed by
# `manage.py audit_worker`. Must be on durable storage in production.
AUDIT_SPOOL_FILE = os.environ.get("AUDIT_SPOOL_FILE", str(BASE_DIR / "audit-spool.jsonl"))
# Only honour X-Forwarded-For when a trusted reverse proxy sets it.
TRUST_PROXY_HEADERS = env_bool("TRUST_PROXY_HEADERS", False)


# ── Regulatory controls ──────────────────────────────────────────────────────

# 21 CFR Part 11 §11.300 / CLIA security expectations.
PASSWORD_EXPIRY_DAYS = int(os.environ.get("PASSWORD_EXPIRY_DAYS", "90"))
PASSWORD_HISTORY_DEPTH = int(os.environ.get("PASSWORD_HISTORY_DEPTH", "5"))
ACCOUNT_LOCKOUT_THRESHOLD = int(os.environ.get("ACCOUNT_LOCKOUT_THRESHOLD", "5"))
ACCOUNT_LOCKOUT_MINUTES = int(os.environ.get("ACCOUNT_LOCKOUT_MINUTES", "30"))
# Idle timeout before the session is terminated (auto-logoff).
IDLE_TIMEOUT_MINUTES = int(os.environ.get("IDLE_TIMEOUT_MINUTES", "20"))
# Require password re-entry when applying an electronic signature (§11.200).
REQUIRE_REAUTH_FOR_SIGNATURE = env_bool("REQUIRE_REAUTH_FOR_SIGNATURE", True)
# Block release of patient results when the day's QC has failed (CLIA §493.1256).
ENFORCE_QC_LOCKOUT = env_bool("ENFORCE_QC_LOCKOUT", True)
# Allow decision rules to release results without a person reading them. Even
# when True, a rule may only release an analyte the laboratory has separately
# approved on its test definition, and every guardrail in
# apps/rules/autoverify.py still applies. Set False to stop all automatic
# release immediately — during a QC investigation, say.
RULES_ALLOW_AUTO_VERIFICATION = env_bool("RULES_ALLOW_AUTO_VERIFICATION", True)

# Where downtime packs are written. This directory holds concentrated patient
# data in a form deliberately readable without the application — see
# apps/operations/continuity.py. Put it on an encrypted volume the laboratory
# physically controls, and make sure it is reachable when the server is not.
DOWNTIME_PACK_DIR = os.environ.get(
    "DOWNTIME_PACK_DIR", str(BASE_DIR / "media" / "downtime")
)

# Where encrypted GDPR subject-access exports are written.
SUBJECT_REQUEST_EXPORT_DIR = os.environ.get(
    "SUBJECT_REQUEST_EXPORT_DIR", str(BASE_DIR / "media" / "subject-requests")
)

# Block validation by staff without current competency (CLIA §493.1451).
ENFORCE_COMPETENCY_GATING = env_bool("ENFORCE_COMPETENCY_GATING", True)
# Prevent the person who entered a result from verifying it (CLIA self-review).
ENFORCE_SELF_VERIFICATION_BLOCK = env_bool("ENFORCE_SELF_VERIFICATION_BLOCK", True)

# ── Observability ────────────────────────────────────────────────────────────
#
# /metrics is Prometheus text exposition and carries counts and states only,
# never identifiers. Leave METRICS_TOKEN unset only when the endpoint is bound
# to an interface the hospital network cannot reach.
METRICS_TOKEN = os.environ.get("METRICS_TOKEN", "")

#: "json" emits one JSON object per line, including the request id, so a log
#: line can be joined to the audit events from the same request.
LOG_FORMAT = os.environ.get("DJANGO_LOG_FORMAT", "text")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"},
        "json": {"()": "apps.operations.observability.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if LOG_FORMAT == "json" else "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "dx": {"level": "DEBUG" if DEBUG else "INFO", "handlers": ["console"], "propagate": False},
        # Rule firings and API traffic are noisy at DEBUG; they inherit "dx".
    },
}
