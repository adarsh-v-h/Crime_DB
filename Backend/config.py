import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def _get_required_env(key):
    """Get a required environment variable or raise error if missing."""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Missing required environment variable: {key}. Please check your .env file.")
    return value

def _get_optional_env(key, default=None):
    """Get an optional environment variable with a default value."""
    return os.getenv(key, default)

# ============================================================================
# DATABASE CONFIGURATION (Required)
# ============================================================================
DB_HOST     = _get_required_env("DB_HOST")
DB_PORT     = int(_get_required_env("DB_PORT"))
DB_USER     = _get_required_env("DB_USER")
DB_PASSWORD = _get_required_env("DB_PASSWORD")
DB_NAME     = _get_required_env("DB_NAME")

# ============================================================================
# FLASK SERVER CONFIGURATION (Required)
# ============================================================================
FLASK_HOST  = _get_required_env("FLASK_HOST")
# Allow either PORT or FLASK_PORT to be set
FLASK_PORT  = int(_get_optional_env("PORT", _get_required_env("FLASK_PORT")))
FLASK_DEBUG = _get_optional_env("FLASK_DEBUG", "false").lower() == "true"

# ============================================================================
# CORS CONFIGURATION (Optional)
# ============================================================================
CORS_ORIGIN = _get_optional_env("CORS_ORIGIN", "*")

# ============================================================================
# reCAPTCHA v2 (Invisible) CONFIGURATION (Required)
# ============================================================================
# All secret/site keys must be provided via environment variables.
# These keys are critical for form security.
RECAPTCHA_SECRET_KEY = _get_required_env("RECAPTCHA_SECRET_KEY")
RECAPTCHA_PUBLIC_KEY = _get_required_env("RECAPTCHA_PUBLIC_KEY")

# ============================================================================
# reCAPTCHA SCORING (Optional - relevant for v3 only)
# ============================================================================
# Note: RECAPTCHA_THRESHOLD is only used for reCAPTCHA v3 scoring
RECAPTCHA_THRESHOLD = float(_get_optional_env("RECAPTCHA_THRESHOLD", "0.5"))

